fetch('/get_link_token')
.then(response => response.json())
.then(data => {
    if (!data.link_token) {
        console.error("Error getting link token:", data);
        return;
    }
    const handler = Plaid.create({
        token: data.link_token,
        onSuccess: function(public_token, metadata) {
            fetch('/exchange_public_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ public_token })
            })

            .then(response => response.json())
            .then(data => {
                if (data.access_token) {
                    console.log(data.access_token);
                    document.getElementById("text").value = "bank connected"
                    document.getElementById("press").src = "../static/assets/img/up.png"
                    document.getElementById("press").style.cursor = "pointer";
                    document.getElementById("press").style.pointerEvents = "auto";
                } else {
                    console.error("Error exchanging public token:", data);
                }
            })
            .catch(error => console.error(error));
        },

        onExit: function(err, metadata) {
            if (err) console.error(err);
        }
    });
    document.getElementById("openPlaid").onclick = async function() {
        handler.open();
        document.getElementById("press").src = "../static/assets/img/loading.gif"
        document.getElementById("press").style.cursor = "default";
        document.getElementById("press").style.pointerEvents = "none";


    };
    document.getElementById("openPlaid2").onclick = async function() {
        handler.open();
        document.getElementById("press").src = "../static/assets/img/loading.gif"
        document.getElementById("press").style.cursor = "default";
        document.getElementById("press").style.pointerEvents = "none";



    };

})
.catch(error => console.error("Error fetching link token:", error));