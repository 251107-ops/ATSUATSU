
function login(){
        let username = document.getElementById("username").value
        let password = document.getElementById("password").value

        if(username=="test" && password=="test123"){
            localStorage.setItem("loginUser",username)
            window.location.href= "index.html"
        }else{
            alert("メールかパスワードが間違ってます")
        }
    }

function greet(){
    let greetinContent = document.getElementById("name")
    let username_save = localStorage.getItem("loginUser")
    if(username_save){
    greetinContent.textContent = greetinContent.textContent.replace("{name}",username_save)
    }else{
        window.location.href = "login.html"
    }
}

function pass_confirm(event){
    let pass1 = document.getElementById("password1").value
    let pass2 = document.getElementById("password2").value

    if(pass1!=pass2){
        event.preventDefault()
       alert("パスワードが一致してない")
    }
    
}