// Switch Tabs
const tabs = document.querySelectorAll(".sidebar button");
const sections = document.querySelectorAll(".content > div");

let fileList = []
let finishList = []
let trans_id = ""

tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        sections.forEach((s) => s.classList.add("hidden"));
        tab.classList.add("active");
        sections[index].classList.remove("hidden");
    });
});

let intervalId; // 用于存储定时器的ID

// 启动定时请求
function startRequest() {
    intervalId = setInterval(async () => {
        const requestOptions = {
            method: "GET",
            redirect: "follow"
        };
        const response = await fetch(`/sqlApi/checkSubtaskStatus?task_id=${trans_id}`, requestOptions)
        const data = await response.json()
        if (data && data.data) {
            finishList = finishList.map(finish => {
                const this_file_name = finish.file.name
                let this_status = 0
                for (let i = 0; i < data.data.length; i++) {
                    const item = data.data[i];
                    if (this_file_name === item[0]) {
                        this_status = item[1];
                        break;
                    }
                }
                return {
                    file: finish.file,
                    status: this_status
                }
            })
        }
        updateAllFile()
    }, 2000);
}

// 停止定时请求
function stopRequest() {
    clearInterval(intervalId);
    const result = document.getElementById("upload-result")
    result.innerHTML = `You can see the results on <a target="_blank" href="/listFiles/${trans_id}">this page</a>`
    console.log(`停止请求: ${intervalId}`);
}

function returnImgUrl(status) {
    status = parseInt(status)
    if (status === 1) {
        return "img/success.svg"
    } else if (status === 2) {
        return "img/error.svg"
    } else {
        return "img/loading.svg"
    }
}


const updateAllFile = () => {
    let allFinish = true;
    finishList.forEach((data) => {
        const logo = document.getElementById(data.file.name);
        logo.src = returnImgUrl(data.status)
        // logo.id = data.file.name;
        logo.style.width = "1.5rem";
        if (data.status === 0) {
            allFinish = false
        }
    });
    if (allFinish) {
        stopRequest()
    }
}

const showAllFile = () => {
    const fileListPlace = document.getElementById("fileList");
    fileListPlace.innerHTML = "";
    finishList.forEach((data) => {
        const div = document.createElement("div");
        const nameDiv = document.createElement("div");
        const logo = document.createElement("img");
        const li = document.createElement("li");
        logo.src = returnImgUrl(data.status)
        logo.id = data.file.name;
        logo.style.width = "1.5rem";
        nameDiv.textContent = data.file.name;
        nameDiv.style.marginLeft = "0.5rem";
        div.appendChild(logo)
        div.appendChild(nameDiv)
        div.style.display = "flex";
        div.style.alignItems = "center";
        fileListPlace.appendChild(li);
        li.appendChild(div);
    });
    fileList.forEach((file) => {
        const li = document.createElement("li");
        li.textContent = file.name;
        const removeBtn = document.createElement("button");
        removeBtn.textContent = "X";
        removeBtn.addEventListener("click", () => {
            fileList = fileList.filter(item => item.name !== file.name)
            li.remove()
        });
        li.appendChild(removeBtn);
        fileListPlace.appendChild(li);
    });
}


// Upload Files
document.getElementById("fileInput").addEventListener("change", async (e) => {
    fileList.push(...e.target.files)
    showAllFile()
});

document.getElementById("uploadFile").addEventListener("click", async (e) => {
    document.getElementById("fileInput").click()
})

document.getElementById("uploadBtn").addEventListener("click", async (e) => {
    const fileListPlace = document.getElementById("fileList");
    const formData = new FormData();

    for (const file of fileList) {
        formData.append("files[]", file);
    }
    formData.append("trans_id", trans_id);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });

    const data = await response.json();
    trans_id = data['output_folder']
    fileList.forEach((file) => {
        finishList.push({
            status: 0,
            file: file
        })

    })
    fileList = []
    fileListPlace.innerHTML = ""; // Clear previous list
    finishList.forEach((data) => {
        const li = document.createElement("li");
        li.textContent = data.file.name;
        fileListPlace.appendChild(li);
    });
    startRequest()
    showAllFile()
});

// Submit URL
document.getElementById("submitUrlBtn").addEventListener("click", async () => {
    const urlInput = document.getElementById("urlInput");
    const urlResult = document.getElementById("urlResult");

    const response = await fetch("/submit_url", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: urlInput.value, trans_id: trans_id}),
    });

    const data = await response.json();
    trans_id = data['output_folder']
});

// Manage QA
document.getElementById("addQaBtn").addEventListener("click", () => {
    const qaContainer = document.getElementById("qaContainer");
    const div = document.createElement("div");
    div.classList.add("qa-pair");
    div.innerHTML = `
        <input type="text" class="q-input" placeholder="Q">
        <input type="text" class="a-input" placeholder="A">
        <button class="removeQaBtn">Remove</button>
    `;
    div.querySelector(".removeQaBtn").addEventListener("click", () => div.remove());
    qaContainer.appendChild(div);
});

document.getElementById("submitQaBtn").addEventListener("click", async () => {
    const qaContainer = document.getElementById("qaContainer");
    const qaPairs = Array.from(qaContainer.querySelectorAll(".qa-pair")).map((pair) => ({
        q: pair.querySelector(".q-input").value,
        a: pair.querySelector(".a-input").value,
    }));

    const response = await fetch("/submit_qa", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({qa_list: qaPairs}),
    });

    const data = await response.json();
    alert(data.message);
});