setInterval(fileUpload, 1000);

async function update() {
    let user = document.getElementById("text").value;
    let file = document.getElementById("file");
    let logs = document.getElementById("logs");

    if (!user.trim() && !file.files.length) return;

    document.getElementById("press").src = "../static/assets/img/loading.gif";
    document.getElementById("press").style.cursor = "default";
    document.getElementById("press").style.pointerEvents = "none";




    let form = new FormData();
    form.append("text", user);
    let fileName = ""
    if (file.files.length > 0) {
        form.append("pdf", file.files[0]);
        fileName = file.files[0].name
        let filefr = await fetch("/save", {
            method: "POST",
            body:form,
        });

    }



    let userMessage = `<div style="display: flex; justify-content: flex-end; margin-bottom: 5px;">
        <div style="width: fit-content; padding: 5px; background-color: darkgray; border-radius: 8px; font-family: verdana;">${user}</div>
    </div>`;
    logs.innerHTML += userMessage;

    document.getElementById("text").value = "";
    file.value = "";
    logs.scrollTop = logs.scrollHeight;

    try {
        let response = await fetch("/advice", {
            method: "POST",
            body: form,
        });

        let chat = await response.json();


        let botMessage = `<div style="display: flex; justify-content: flex-start; margin-bottom: 5px;">
            <div style="color: white; width: fit-content; max-width: 500px; padding: 5px; background-color: black; border-radius: 8px; font-family: verdana;">${chat.reply}</div>
        </div>`;





        logs.innerHTML += botMessage;
        logs.scrollTop = logs.scrollHeight;
        document.getElementById("press").src = "../static/assets/img/up.png"
        document.getElementById("press").style.cursor = "pointer";
        document.getElementById("press").style.pointerEvents = "auto";
    } catch (error) {
        let errorMessage = `<div style="display: flex; justify-content: flex-start; margin-bottom: 5px;">
            <div style="border:2px solid black; width: fit-content;  padding: 5px; background-color: lightcoral; border-radius: 8px;">Failed to connect to the server.</div>
        </div>`;

        logs.innerHTML += errorMessage;
    }
}

async function fileUpload() {
    let file = document.getElementById("file");
    let fileName = ""
    if (file.files.length > 0) {
        fileName = file.files[0].name
        document.getElementById("text").value = fileName
    }
}
