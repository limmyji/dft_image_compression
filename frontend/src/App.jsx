import Gallery from './Gallery';
import { useState, useEffect } from 'react';

function App() {
  const [curUser, setCurUser] = useState("");
  const [curToken, setCurToken] = useState("");
  const [typedUsernameLogin, setTypedUsernameLogin] = useState("");
  const [typedPassLogin, setTypedPassLogin] = useState("");
  const [typedUsernameReg, setTypedUsernameReg] = useState("");
  const [typedPassReg, setTypedPassReg] = useState("");

  // see if user is already logged in on the first render
  useEffect(() => {
    if (localStorage.getItem("curUser") && localStorage.getItem("curToken")){
      setCurUser(localStorage.getItem("curUser"));
      setCurToken(localStorage.getItem("curToken"));
    }
  }, [])

  // handle login
  const handleLogin = async(event) => {
    event.preventDefault();
  
    // make sure typed user/pass are not empty
    if (typedUsernameLogin.length === 0 || typedPassLogin.length === 0){
      alert("Username and password must not be empty!");
      return;
    }

    // send req to backend with details to get jwt token
    try {
        const response = await fetch(`http://127.0.0.1:8000/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ username: typedUsernameLogin, password: typedPassLogin }),
        });

        if (!response.ok) {
            throw new Error("Failed to login, try again.");
        }
        const data = await response.json();

        // if we got token, successful login
        if (data.jwt){
          setCurUser(typedUsernameLogin);
          setCurToken(data.jwt);
          localStorage.setItem("curUser", typedUsernameLogin);
          localStorage.setItem("curToken", data.jwt);
          setTypedUsernameLogin("");
          setTypedPassLogin("");
          alert("Logged in!");
        } else {
          alert("Wrong username or password!");
        }
    } catch (error) {
        console.error("Error logging in: ", error);
    }
  }

  // handle register
  const handleRegister = async(event) => {
    event.preventDefault();

    // make sure typed user/pass are not empty
    if (typedUsernameReg.length === 0 || typedPassReg.length === 0){
      alert("Username and password must not be empty!");
      return;
    }

    // send req to backend to register
    try {
        const response = await fetch(`http://127.0.0.1:8000/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ username: typedUsernameReg, password: typedPassReg }),
        });

        // if reponse is good, then registration went through
        if (!response.ok) {
            throw new Error("Failed to register, try again.");
        }

        setTypedUsernameReg("");
        setTypedPassReg("");
        alert("Registered!");
        
    } catch (error) {
        console.error("Error registering: ", error);
    }
  }

  // handle logout, clear cur username and token
  const handleLogout = async(event) => {
    event.preventDefault();
    setCurUser("");
    setCurToken("");
    localStorage.setItem("curUser", "");
    localStorage.setItem("curToken", "");
    alert(`Logged Out!`);
  }

  const handleUserChangeLogin = (event) => {
    setTypedUsernameLogin(event.target.value);
  }

  const handlePassChangeLogin = (event) => {
    setTypedPassLogin(event.target.value);
  }

  const handleUserChangeReg = (event) => {
    setTypedUsernameReg(event.target.value);
  }

  const handlePassChangeReg = (event) => {
    setTypedPassReg(event.target.value);
  }

  return (
    <div>
      {(curUser !== "" && curToken !== "") ? (
          <>
            {/* if we are logged in with a username and token, display the dashboard with a logout button */}
            <button onClick={handleLogout}>Log Out</button>
            <Gallery
              curUser={curUser}
              curToken={curToken}
            />
          </>
        ) : (
          <>
            {/* else, display the forms to login/register */}
            <h1>Please Log In!</h1>
            <h3>Log In:</h3>
            <form onSubmit={handleLogin}>
                <p>Username:</p>
                <textarea
                    name="username"
                    value={typedUsernameLogin}
                    onChange={handleUserChangeLogin}
                />

              <p>Password:</p>
                <textarea
                    name="password"
                    value={typedPassLogin}
                    onChange={handlePassChangeLogin}
                />
                <button type="submit">Log In</button>
            </form>

            <h3>Register:</h3>
            <form onSubmit={handleRegister}>
                <p>Username:</p>
                <textarea
                    name="username"
                    value={typedUsernameReg}
                    onChange={handleUserChangeReg}
                />

              <p>Password:</p>
                <textarea
                    name="password"
                    value={typedPassReg}
                    onChange={handlePassChangeReg}
                />
                <button type="submit">Register</button>
            </form>
          </>
      )}
    </div>
  );
}

export default App;
