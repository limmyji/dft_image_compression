function Image({ link }) {
    // display the image neatly
    return(
        <li>
            {/* display image, save aws req for now */}
            {/* <img src={link} /> */}
            <p>{link}</p>
        </li>
    );
}

export default Image;
