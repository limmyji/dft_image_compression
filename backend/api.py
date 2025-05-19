from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import numpy as np
from io import BytesIO
import compress_shared
import uuid
import boto3
import os
from tempfile import NamedTemporaryFile
import psycopg2
import psycopg2.extras
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import jwt
import time
from pydantic import BaseModel

# aws s3 config
bucket = os.getenv("aws_bucket_name")
region = os.getenv("aws_bucket_region")
os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("aws_access_key_id")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("aws_secret_access_key")
s3 = boto3.client("s3", region_name=region)

# postgresql config
hostname = os.getenv("hostname")
database = os.getenv("database")
user = os.getenv("user")
port = os.getenv("port")
pwd = os.getenv("pwd")

# priv/pub keys
priv = os.getenv("priv")
pub = os.getenv("pub")

# connect to postgres while app is running
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.db_connection = psycopg2.connect(
        host = hostname,
        dbname = database,
        user = user,
        password = pwd,
        port = port
    )
    yield
    app.db_connection.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# access postgres within requests
def get_db():
    db = app.db_connection
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        yield cursor
    finally:
        cursor.close()


class register_req(BaseModel):
    username: str
    password: str

# register user, assume password is hashed on client side
@app.post("/register")
async def register_user(data: register_req, db: Session = Depends(get_db)):
    username = data.username
    password = data.password

    # username is valid
    if len(username) > 20 or len(username) < 1:
        raise HTTPException(status_code=400, detail="username invalid!")
    # username doesnt already exist
    db.execute("SELECT EXISTS (SELECT 1 FROM users WHERE username = %s);", (username,))
    if db.fetchone()[0]:
        raise HTTPException(status_code=400, detail="username exists!")
    
    # else add user to db
    try:
        db.execute("INSERT INTO users (username, password) VALUES (%s, %s);", (username, password,))
        app.db_connection.commit()

        return({"message": "registration successful!"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


class login_req(BaseModel):
    username: str
    password: str

# log in user, if provided username and hashed password line up, return a jwt token w/ username as payload
@app.post("/login")
async def login(data: login_req, db: Session = Depends(get_db)):
    username = data.username
    password = data.password

    # user doesnt exist
    db.execute("SELECT EXISTS (SELECT 1 FROM users WHERE username = %s);", (username,))
    if not db.fetchone()[0]:
        return({"message": "incorrect username or password!"})
    
    # else check if hashed password is correct
    try:
        db.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = db.fetchone()
        if row["password"] == password:
            encoded = jwt.encode({"username": username, "exp": time.time() + 3600}, priv, algorithm="RS256")

            # return the encoded session token
            return({"message": "login successful!", "jwt": encoded})
        else:
            return({"message": "incorrect username or password!"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# get all users files on the server
@app.get("/get_images")
async def get_images(username: str, token: str, db: Session = Depends(get_db)):
    # user exists
    db.execute("SELECT EXISTS (SELECT 1 FROM users WHERE username = %s);", (username,))
    if not db.fetchone()[0]:
        raise HTTPException(status_code=400, detail="user doesnt exist!")
    
    # make sure is actually a jwt that isnt expired
    try:
        decoded = jwt.decode(token, pub, algorithms=["RS256"])
    except (jwt.exceptions.DecodeError, jwt.exceptions.ExpiredSignatureError) as e:
        raise HTTPException(status_code=403, detail="invalid token, try loging in again")
    # make sure username is in the payload
    if "username" not in decoded or decoded["username"] != username:
        raise HTTPException(status_code=403, detail="invalid token, try loging in again")
    
    # get user's images
    try:
        db.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = db.fetchone()

        # return as a row of presigned urls to the frontend
        presigned_urls = []
        for image in row["images"]:
            presigned_urls.append(s3.generate_presigned_url('get_object', Params={"Bucket": bucket, "Key": image}))
        return({"message": "retrived images!", "images": presigned_urls, "image_names": row["images"]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# compress an uploaded image, upload compressed version to s3, return s3 key of the compressed image
@app.post("/compress_img")
async def compress_img(username: str = Form(...), greyscale: bool = Form(...), token: str = Form(...), 
                       file: UploadFile = File(...), db: Session = Depends(get_db)):
    # make sure we have a image
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="not a image...")

    # user exists
    db.execute("SELECT EXISTS (SELECT 1 FROM users WHERE username = %s);", (username,))
    if not db.fetchone()[0]:
        raise HTTPException(status_code=400, detail="user doesnt exist!")
    
    # make sure is actually a jwt that isnt expired
    try:
        decoded = jwt.decode(token, pub, algorithms=["RS256"])
    except (jwt.exceptions.DecodeError, jwt.exceptions.ExpiredSignatureError) as e:
        raise HTTPException(status_code=403, detail="invalid token, try loging in again")
    # make sure username is in the payload
    if "username" not in decoded or decoded["username"] != username:
        raise HTTPException(status_code=403, detail="invalid token, try loging in again")

    try:
        # read the image, convert to numpy array
        image_data = await file.read()
        image = Image.open(BytesIO(image_data))
        if greyscale:
            image = image.convert("L")
        image_array = np.array(image)

        # compress image, give unique filename
        compressed = compress_shared.compress_image(image=image_array, greyscale=greyscale)
        filename = str(uuid.uuid4()) + ".jpg"

        # upload compressed image to s3
        bits = BytesIO()
        Image.fromarray(compressed).save(bits, format="JPEG")
        bits.seek(0)
        s3.upload_fileobj(bits, Bucket=bucket, Key=filename)

        # add filename under the user's images in db, res filename
        update_script = "UPDATE users SET images = ARRAY_APPEND(images, %s) WHERE username = %s;"
        db.execute(update_script, (filename, username,))
        app.db_connection.commit()
        return({"filename": filename})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# compress an uploaded vid, upload compressed vid to s3, return s3 key of compressed vid
@app.post("/compress_vid")
async def compess_vid(greyscale: bool, file: UploadFile = File(...)):
    # make sure we have a video
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="not a vid...")
    
    # save video locally using temp file
    try:
        temp = NamedTemporaryFile(delete=False, dir="./temp")
        contents = file.file.read()
        with temp as f:
            f.write(contents)

    # close file
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()

    # compress the temp file and upload to s3
    try:
        # turn vid into array of frames, then compress array of frames, save compressed vid as tempfile
        frames = compress_shared.video_to_frames(path=temp.name, greyscale=greyscale)
        filename = str(uuid.uuid4()) + ".mp4"
        compress_shared.compress_video(frames=frames, out_name="./temp/" + filename, greyscale=greyscale)

        # upload compressed video to s3
        s3.upload_file(Filename="./temp/" + filename, Bucket=bucket, Key=filename)

        # res filename
        return({"filename": filename})
    
    # del temp files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(temp.name)
        os.remove("./temp/" + filename)
