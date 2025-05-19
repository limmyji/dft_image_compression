import numpy as np
import scipy as sci
from PIL import Image
import cv2
import boto3
from io import BytesIO
from dotenv import load_dotenv
import os

load_dotenv()

bucket = os.getenv("aws_bucket_name")
region = os.getenv("aws_bucket_region")
os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("aws_access_key_id")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("aws_secret_access_key")
s3 = boto3.client("s3", region_name=region)

# "compress" x, based on tol
# x is a 2d numpy array, 0 <= tol <= 1
def compress(x, tol=0.001):
    # perform a fourier transform on the grid, turning it to frequency data
    cur_fft = sci.fft.fft2(x)
    # let our tolerance be tol * <max element maginitute in the grid>
    cur_tol = tol * np.max(np.abs(cur_fft))

    # 0 out any entries with magnitute < tolerance
    cur_fft[np.abs(cur_fft) <= cur_tol] = 0

    # inverse fourier transform to get output image, 0 out imaginary parts due to rounding errors
    return(np.real(sci.fft.ifft2(cur_fft)))


# given a aws s3 path or image grid, compress the image
def compress_image(image=None, path=None, greyscale=False):
    # greyscale
    if greyscale:
        # load image from path, covert to a grid of greyscale values
        if path is not None:
            # get image from s3
            obj = s3.get_object(Bucket=bucket, Key=path)
            image = Image.open(BytesIO(obj["Body"].read())).convert("L")
            image = np.array(image)

        # compress the gresycale grid
        output = compress(image)
        output_image = np.clip(output,0, 255).astype(np.uint8)

    # rgb
    else:
        # load image from path, covert to a grid of RGB tuples
        if path is not None:
            # get image from s3
            obj = s3.get_object(Bucket=bucket, Key=path)
            image = Image.open(BytesIO(obj["Body"].read())).convert("RGB")
            image = np.array(image)

        # split into 3 grids, of R, G, B values
        R = image[:, :, 0]
        G = image[:, :, 1]
        B = image[:, :, 2]
        # compress each individual grid
        R = compress(R)
        G = compress(G)
        B = compress(B)

        # reconstruct compresssed image
        output = np.stack([R, G, B], axis=-1)
        output_image = np.clip(output,0, 255).astype(np.uint8)

    # return compressed image
    return(np.array(output_image))


# take a video and convert it into an array of frames
def video_to_frames(path, fps=10, greyscale=False):
    # load from temp file and get its fps
    vid = cv2.VideoCapture(path)
    og_fps = vid.get(cv2.CAP_PROP_FPS)
    
    # frames will be an array of saved frames
    # only save every og_fps/fps frame, since we want to specify the fps
    frame_interval = int(og_fps / fps)
    frames = []
    total_frames = 0

    # open the video, look at each frame
    while vid.isOpened():
        # if end of video
        ret, frame = vid.read()
        if not ret:
            break

        # if the current frame"s index is a multiple of the frame interval, save it
        if total_frames % frame_interval == 0:
            # greyscale
            if greyscale:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            # rgb
            else:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        total_frames += 1

    # return as np array
    vid.release()
    return(np.array(frames))


# take an array of frames, compress each frame and convert it into a video
def compress_video(frames, out_name, fps=10, greyscale=False):
    # dimensions of the video
    if greyscale:
        height, width = frames[0].shape
    else:
        height, width, _ = frames[0].shape

    # output format, file it will be written to
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_name, fourcc, fps, (width, height))

    # compress + format each frame
    for frame in frames:
        # greyscale
        if greyscale:
            out.write(cv2.cvtColor(compress_image(image=frame, greyscale=greyscale), cv2.COLOR_GRAY2BGR))
        # rgb
        else:
            out.write(cv2.cvtColor(compress_image(image=frame, greyscale=greyscale), cv2.COLOR_RGB2BGR))
    out.release()
