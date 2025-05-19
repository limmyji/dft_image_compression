import Image from './Single';
import { useState, useEffect } from 'react';

function Gallery({ curUser, curToken }) {
    const [images, setImages] = useState([]);
    const [imageNames, setImageNames] = useState([]);
    const [cahcedImages, setCachedImages] = useState([]);
    const [newImage, setNewImage] = useState("");
    const [selectedFile, setSelectedFile] = useState(null);
    const [greyscale, setGreyscale] = useState(false);

    // upon load, fetch upload images from backend
    useEffect(() => {
        fetch(`http://127.0.0.1:8000/get_images?username=${curUser}&token=${curToken}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`error: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                setImages(data.images);
                setImageNames(data.image_names);
            })
            .catch(error => {
                console.error("error fetching images:", error);
            });
    }, [newImage]);

    // take an image and compress it
    const handleCompress = async(event) => {
        event.preventDefault();
    
        // make sure we have a file
        if (!selectedFile) {
            alert("please select a file to upload.");
            return;
        }

        // send req to backend to compress this file (will only succeed with images)
        const formData = new FormData();
        formData.append("username", curUser);
        formData.append("greyscale", greyscale);
        formData.append("token", curToken);
        formData.append("file", selectedFile);
        
        try {
            const response = await fetch(`http://127.0.0.1:8000/compress_img`, {
                method: "POST",
                body: formData,
            });

            // if response is ok, compression worked
            if (!response.ok) {
                throw new Error("Failed to upload image.");
            }
            const data = await response.json();
            setNewImage(data.filename);
            alert("image compressed!");

        } catch (error) {
            console.error("error compressing image: ", error);
        }
    }

    const handleFileChange = (event) => {
        setSelectedFile(event.target.files[0]);
    }

    const handleGreyscaleSwap = () => {
        setGreyscale(!(greyscale));
    }
    
    return (
        <>
            {/* compress new image form */}
            <h3>Compress new image</h3>
            <form onSubmit={handleCompress}>
                <input type="file" accept="image/*" onChange={handleFileChange} />
                <button type="submit">Upload</button>
            </form>
            {/* enable/disable greyscale */}
            <button onClick={handleGreyscaleSwap}>
                {`Greyscale is set to ${greyscale}, click to set to ${!(greyscale)}`}
            </button>

            {(images.length !== 0) ? (
                <>
                    {/* if we have images, display */}
                    <ul>
                        {images.map((element) => (
                            <Image key={element} link={element} />
                        ))}
                    </ul>
                </>
                ) : (
                <>
                    {/* else display text */}
                    <h1>No Images Yet!</h1>
                </>
                )
            }
        </>
    );
}

export default Gallery;
