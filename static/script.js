// Switch Tabs
const tabs = document.querySelectorAll(".sidebar button");
const sections = document.querySelectorAll(".content > div");
const submitAll = document.getElementById("submit-all");

let fileList = []
let finishList = []
let collection_name = ""
let trans_id = ""
let queryUrl = ""
let queryUrlStatus = null
let click_tab = 1

tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        sections.forEach((s) => s.classList.add("hidden"));
        tab.classList.add("active");
        click_tab = index;
        sections[index].classList.remove("hidden");
        sections[4].classList.remove("hidden");
    });
});

let intervalId;

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
                const this_file_name = finish.save_file_name
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
                    save_file_name: finish.save_file_name,
                    status: this_status
                }
            })
            try {
                const urlLogo = document.getElementById("url-logo")
                for (let i = 0; i < data.data.length; i++) {
                    const item = data.data[i];
                    if (queryUrl === item[0]) {
                        urlLogo.src = returnImgUrl(item[1])
                        queryUrlStatus = item[1];
                        break;
                    }
                }
            } catch (e) {
            }
        }
        updateAllFile()
    }, 2000);
}

function startAllRequest() {
    intervalId = setInterval(async () => {
        const requestOptions = {
            method: "GET",
            redirect: "follow"
        };
        const response = await fetch(`/sqlApi/checkTaskStatus?task_id=${trans_id}`, requestOptions)
        const data = await response.json()
        if (data && data.data) {
            const logo = document.getElementById("submit-all-logo")
            const thisStatus = parseInt(data.data[0])
            logo.src = returnImgUrl(thisStatus)
            logo.style.width = "3rem";
            logo.style.marginRight = "0.5rem";
            if (thisStatus !== 0) {
                clearInterval(intervalId);
            }
        }

    }, 2000);
}

document.getElementById("collectionName").addEventListener("input", (e) => {
    const c = document.getElementById("container")
    if (e.target.value !== "") {
        collection_name = e.target.value
        c.style.pointerEvents = "auto";
        c.style.opacity = "1";
        c.style.userSelect = "auto";
    } else {
        c.style.pointerEvents = "none";
        c.style.opacity = "0.5";
        c.style.userSelect = "none";
    }
})

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
        const logo = document.getElementById(data.save_file_name);
        logo.src = returnImgUrl(data.status)
        // logo.id = data.file.name;
        logo.style.width = "1.5rem";
        if (data.status === 0) {
            allFinish = false
        }
    });
    if (allFinish && queryUrlStatus !== 0 && (queryUrl === "" || queryUrlStatus !== null)) {
        canSubmit()
        stopRequest()
    }
}

const canSubmit = () => {
    submitAll.disabled = false;
    submitAll.style.opacity = '1';
    submitAll.style.cursor = "pointer";
}

const cannotSubmit = () => {
    submitAll.disabled = true;
    submitAll.style.opacity = '0.5';
    submitAll.style.cursor = "not-allowed";
}

cannotSubmit()

const showAllFile = () => {
    const fileListPlace = document.getElementById("fileList");
    fileListPlace.innerHTML = "";
    finishList.forEach((data) => {
        const div = document.createElement("div");
        const nameDiv = document.createElement("div");
        const logo = document.createElement("img");
        const li = document.createElement("li");
        logo.src = returnImgUrl(data.status)
        logo.id = data.save_file_name;
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

    cannotSubmit()

    for (const file of fileList) {
        formData.append("files[]", file);
    }
    if(trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }
    formData.append("trans_id", trans_id);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });
    document.getElementById("collectionName").disabled = true;

    const data = await response.json();
    const file_name_list = data['file_name_list']
    fileListPlace.innerHTML = ""; // Clear previous list
    fileList.forEach((file) => {
        const fileName = file.name;
        let index = file_name_list.findIndex(item => item.name === fileName);

        if (index !== -1) {
            let renameValue = file_name_list[index].rename;
            file_name_list.splice(index, 1);
            finishList.push({
                status: 0,
                save_file_name: renameValue,
                file: file
            })
        }
    })
    fileList = []
    showAllFile()
    startRequest()
});

// Submit URL
document.getElementById("submitUrlBtn").addEventListener("click", async () => {
    const urlInput = document.getElementById("urlInput");
    const urlResult = document.getElementById("urlResult");

    const logo = document.getElementById("url-logo");

    logo.src = returnImgUrl(0)
    logo.style.width = "1.5rem";
    logo.style.marginRight = "0.5rem";

    urlInput.disabled = true;

    urlInput.parentNode.insertBefore(logo, urlInput);

    document.getElementById("collectionName").disabled = true;

    cannotSubmit()

    queryUrl = urlInput.value

    if(trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }

    const response = await fetch("/submit_url", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: queryUrl, trans_id: trans_id}),
    });

    const data = await response.json();
    trans_id = data['output_folder']

    startRequest()
});

const checkAllQA = () => {
    let checkStatus = false
    const qaContainer = document.getElementById("qaContainer");
    Array.from(qaContainer.querySelectorAll(".qa-pair")).forEach((pair) => {
        const q = pair.querySelector(".q-input").value
        const a = pair.querySelector(".a-input").value
        if(q && a){
            checkStatus = true
        }
    });
    if(checkStatus) {
        canSubmit()
    }
    return checkStatus
}

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
    div.querySelector(".q-input").addEventListener("input", () => checkAllQA());
    div.querySelector(".a-input").addEventListener("input", () => checkAllQA());
    div.querySelector(".removeQaBtn").addEventListener("click", () => div.remove());
    qaContainer.appendChild(div);
});

const qaContainer = document.getElementById("qaContainer");
qaContainer.querySelector(".q-input").addEventListener("input", () => checkAllQA());
qaContainer.querySelector(".a-input").addEventListener("input", () => checkAllQA());

document.getElementById("submit-all").addEventListener("click", async () => {
    const qaContainer = document.getElementById("qaContainer");
    let qaPairs = []
    Array.from(qaContainer.querySelectorAll(".qa-pair")).forEach((pair) => {
        const q = pair.querySelector(".q-input").value
        const a = pair.querySelector(".a-input").value
        if(q && a) {
            qaPairs.push({
                question: q,
                answer: a
            })
        }
    });
    document.getElementById("submit-all").disabled = true;
    const logo = document.getElementById("submit-all-logo")
    logo.src = returnImgUrl(0)
    logo.style.width = "3rem";
    logo.style.marginRight = "0.5rem";
    const result = document.getElementById("upload-result")
    result.innerHTML = ""
    if(trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }
    const response = await fetch("/submit_all_data", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({trans_id: trans_id, collection_name: collection_name, qa_list: qaPairs}),
    });

    const data = await response.json();

    document.getElementById("submit-text").style.display = "block";

    startAllRequest();
});