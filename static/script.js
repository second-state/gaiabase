// Switch Tabs
const tabs = document.querySelectorAll(".sidebar button");
const sections = document.querySelectorAll(".content > div");
const submitAll = document.getElementById("submit-all");

let urlList = []
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

let fileIntervalId;
let urlIntervalId;
let allIntervalId;

const socket = io.connect('http://127.0.0.1:519');

// 监听文件处理完成
socket.on('file_processed', data => {
    const thisQaPlace = document.getElementById(`qa_${data.file_name}`)
    const thisQaList = document.createElement(`div`)
    thisQaList.id = `qaList_${data.file_name}`
    thisQaPlace.style.display = "block";
    thisQaPlace.innerHTML = ""
    const question = document.createElement('div');
    const answer = document.createElement('div');
    const skip = document.createElement('button');
    const yes = document.createElement('button');
    question.textContent = "Do you need to preview the generated QAs?"
    thisQaPlace.appendChild(question)
    answer.style.display = "flex";
    skip.textContent = "Skip"
    skip.onclick = () => {
        thisQaPlace.style.display = "none";
    }
    yes.textContent = "Preview"
    yes.onclick = () => {
        thisQaList.style.display = "block";
        document.getElementById("container").style.display = "none";
        document.getElementById("submit-all-place").style.display = "none";
    }
    answer.appendChild(skip)
    answer.appendChild(yes)
    thisQaPlace.appendChild(answer)
    const fileName = document.createElement('a');
    fileName.textContent = "Source text: " + data.old_name;
    fileName.href = `/files/${trans_id}/${data.file_name}`;
    fileName.target = "_black";
    const QAList = document.createElement('div');
    QAList.id = "allQAList"
    const saveButton = document.createElement('button');
    saveButton.textContent = "save all QA"
    saveButton.onclick = () => {
        thisQaPlace.style.display = "none";
        thisQaList.style.display = "none";
        document.getElementById("container").style.display = "flex";
        document.getElementById("submit-all-place").style.display = "flex";
    }
    Object.keys(data.qa_list).forEach(key=>{
        if(key.startsWith("qa")) {
            const splitData = data.qa_list[key].split(":\n")
            const QA = document.createElement('div');
            const Q = document.createElement('textarea');
            const A = document.createElement('textarea');
            QA.style.display = "flex";
            QA.style.marginBottom = "0.5rem";
            Q.style.flex = "1";
            Q.rows = 3;
            A.style.flex = "1";
            A.rows = 3;
            Q.className = "question"
            Q.value = splitData[0]
            A.className = "answer"
            A.value = splitData[1]
            QA.appendChild(Q)
            QA.appendChild(A)
            QAList.appendChild(QA)
        }
    })
    thisQaList.appendChild(fileName)
    thisQaList.appendChild(QAList)
    thisQaList.appendChild(QAList)
    thisQaList.appendChild(saveButton)
    thisQaList.style.display = "none";
    document.getElementById("allQAListPlace").appendChild(thisQaList)
});

function startUrlRequest() {
    urlIntervalId = setInterval(async () => {
        const requestOptions = {
            method: "GET",
            redirect: "follow"
        };
        const response = await fetch(`/sqlApi/checkCrawlUrlSubtaskStatus?task_id=${trans_id}`, requestOptions)
        const data = await response.json()
        if (data && data.data) {
            try {
                const result = {};
                for (let i = 0; i < data.data.length; i++) {
                    const item = data.data[i];
                    const id = item[0]
                    if (!result[id]) {
                        result[id] = [];
                    }
                    result[id].push(item[2]);
                    console.log("curl-" + item[1])
                    document.getElementById("cUrl-" + item[1]).src = returnImgUrl(item[2])
                }
                let all_ok = true;
                Object.keys(result).forEach(id => {
                    const urlLogo = document.getElementById("url-" + id)
                    const statuses = result[id];
                    if (statuses.includes(0)) {
                        urlLogo.src = returnImgUrl(0)
                        all_ok = false;
                    } else if (statuses.includes(2)) {
                        urlLogo.src = returnImgUrl(2)
                    } else {
                        urlLogo.src = returnImgUrl(1)
                    }
                    if (all_ok) {
                        canSubmit()
                        clearInterval(urlIntervalId);
                    }
                });
            } catch (e) {
                console.log(e)
            }
        }
    }, 2000);
}

function startRequest() {
    fileIntervalId = setInterval(async () => {
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
                let word_count = 0
                for (let i = 0; i < data.data.length; i++) {
                    const item = data.data[i];
                    if (this_file_name === item[0]) {
                        this_status = item[1];
                        word_count = item[2];
                        break;
                    }
                }
                return {
                    file: finish.file,
                    save_file_name: finish.save_file_name,
                    status: this_status,
                    word_count: word_count
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
    allIntervalId = setInterval(async () => {
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
                clearInterval(allIntervalId);
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

document.getElementById("splitLength").addEventListener("input", (e) => {
    updateAllFile()
})

// 停止定时请求
function stopRequest() {
    clearInterval(fileIntervalId);
    const result = document.getElementById("upload-result")
    result.innerHTML = `You can see the results on <a target="_blank" href="/listFiles/${trans_id}">this page</a>`
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
        const logo = document.getElementById("logo_" + data.save_file_name);
        const word_count_div = document.getElementById("count_" + data.save_file_name);
        logo.src = returnImgUrl(data.status)
        // logo.id = data.file.name;
        logo.style.width = "1.5rem";
        if (data.word_count) {
            word_count_div.innerText = "word count: " + data.word_count
        }
        const div = document.getElementById("input_" + data.save_file_name)
        if (data.status === 0) {
            allFinish = false
        } else if (data.status === 1 && !data.file.name.endsWith(".ttl")) {
            if(parseInt(data.word_count) > 400) {
                const thisQaPlace = document.getElementById(`qa_${data.save_file_name}`)
                const qaPlace = document.createElement("div");
                const qaText = document.createElement("div");
                const qaLogo = document.createElement("img");
                qaLogo.src = returnImgUrl(0)
                qaLogo.style.width = "1.5rem";
                qaLogo.style.marginRight = "0.4rem";
                qaText.textContent = "waiting for summarize~"
                qaPlace.appendChild(qaLogo)
                qaPlace.appendChild(qaText)
                qaPlace.style.display = "flex"
                thisQaPlace.innerHTML = ""
                thisQaPlace.appendChild(qaPlace)
                thisQaPlace.style.display = "block";
            }
            if (parseInt(data.word_count) <= document.getElementById("splitLength").value) {
                div.style.display = "block";
            } else {
                div.style.display = "none";
            }
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


const addFinishFile = (rename, fileName) => {
    const fileListPlace = document.getElementById("finishFileList");
    const div = document.createElement("div");
    const word_count_div = document.createElement("div");
    const nameDiv = document.createElement("a");
    const logo = document.createElement("img");
    const li = document.createElement("li");
    const qa_div = document.createElement('div');
    const input_div = document.createElement('div');
    const span = document.createElement('span');
    const textarea = document.createElement('textarea');
    textarea.name = rename;
    textarea.id = rename;
    textarea.style.width = '100%';
    textarea.style.height = '3rem';
    textarea.style.padding = '0.4rem';
    textarea.style.marginTop = '0.2rem';
    span.innerText = "Summarizing " + fileName + " document:";
    qa_div.id = "qa_" + rename;
    qa_div.style.marginBottom = "0.5rem";
    qa_div.style.display = "none";
    input_div.id = "input_" + rename;
    input_div.style.display = "none";
    input_div.appendChild(span);
    input_div.appendChild(textarea);
    logo.src = returnImgUrl(0)
    word_count_div.id = "count_" + rename;
    word_count_div.style.marginLeft = "0.5rem";
    logo.id = "logo_" + rename;
    logo.style.width = "1.5rem";
    nameDiv.textContent = fileName;
    nameDiv.href = `/files/${trans_id}/${rename}`;
    nameDiv.target = "_black";
    nameDiv.style.marginLeft = "0.5rem";
    div.appendChild(logo)
    div.appendChild(nameDiv)
    div.appendChild(word_count_div)
    div.style.display = "flex";
    div.style.alignItems = "center";
    li.appendChild(div);
    fileListPlace.appendChild(li);
    fileListPlace.appendChild(qa_div);
    fileListPlace.appendChild(input_div);
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
    if (trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }

    formData.append("trans_id", trans_id);
    formData.append("ttl_type", document.getElementById("ttl-text").checked ? "text" : "md");

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });
    document.getElementById("collectionName").disabled = true;
    document.getElementById("ttl-text").disabled = true;
    document.getElementById("ttl-md").disabled = true;

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
            addFinishFile(renameValue, fileName)
        }
    })
    fileList = []
    startRequest()
});

// Submit URL
document.getElementById("submitUrlBtn").addEventListener("click", async () => {
    const urlInput = document.getElementById("urlInput");
    const submitUrlBtn = document.getElementById("submitUrlBtn");
    const urlListPlace = document.getElementById("urlList");


    document.getElementById("collectionName").disabled = true;
    document.getElementById("ttl-text").disabled = true;
    document.getElementById("ttl-md").disabled = true;

    cannotSubmit()

    urlInput.disabled = true
    submitUrlBtn.disabled = true

    queryUrl = urlInput.value

    if (trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }

    const response = await fetch("/submit_url", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: queryUrl, trans_id: trans_id}),
    });

    const data = await response.json();
    const url_id = data['id']
    const mapUrlList = data['mapUrlList']

    urlList.push({id: url_id, url: queryUrl, status: 0})
    const li = document.createElement("li");
    const logo = document.createElement("img");
    const flexDiv = document.createElement("div");
    const div = document.createElement("div");
    logo.id = "url-" + url_id;
    logo.src = returnImgUrl(0)
    logo.style.width = "1.5rem";
    logo.style.marginRight = "0.3rem";
    flexDiv.style.display = "flex";
    flexDiv.style.alignItems = "center";
    div.textContent = queryUrl;
    flexDiv.appendChild(logo)
    flexDiv.appendChild(div)
    li.appendChild(flexDiv)
    const ul = document.createElement("ul");
    ul.id = "ul-" + url_id
    ul.style.paddingTop = "0.5rem"
    mapUrlList.forEach((mapUrl) => {
        const liNext = document.createElement("li");
        const cDiv = document.createElement("div");
        const cLogo = document.createElement("img");
        cLogo.id = "cUrl-" + mapUrl.id;
        cLogo.src = returnImgUrl(0)
        cLogo.style.width = "1rem";
        cLogo.style.marginRight = "0.2rem";
        cDiv.textContent = mapUrl.url;
        liNext.style.display = "flex";
        liNext.style.justifyContent = "left";
        liNext.style.alignItems = "center";
        liNext.appendChild(cLogo)
        liNext.appendChild(cDiv)
        ul.appendChild(liNext)
    })
    li.appendChild(ul)
    urlListPlace.appendChild(li);
    urlInput.disabled = false
    submitUrlBtn.disabled = false
    startUrlRequest()
});

const checkAllQA = () => {
    let checkStatus = false
    const qaContainer = document.getElementById("qaContainer");
    const embedContainer = document.getElementById("embedContainer");
    Array.from(qaContainer.querySelectorAll(".qa-pair")).forEach((pair) => {
        const q = pair.querySelector(".q-input").value
        const a = pair.querySelector(".a-input").value
        if (q && a) {
            checkStatus = true
        }
    });
    Array.from(embedContainer.querySelectorAll(".embed-pair")).forEach((pair) => {
        const q = pair.querySelector(".embed-q-input").value
        const a = pair.querySelector(".embed-a-input").value
        if (q && a) {
            checkStatus = true
        }
    });
    if (checkStatus) {
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

// Manage QA
document.getElementById("addEmbedBtn").addEventListener("click", () => {
    const qaContainer = document.getElementById("embedContainer");
    const div = document.createElement("div");
    div.classList.add("embed-pair");
    div.innerHTML = `
        <textarea class="embed-q-input" placeholder="short text"></textarea>
        <textarea class="embed-a-input" placeholder="long text"></textarea>
        <button class="removeEmbedQaBtn">Remove</button>
    `;
    div.querySelector(".embed-q-input").addEventListener("input", () => checkAllQA());
    div.querySelector(".embed-a-input").addEventListener("input", () => checkAllQA());
    div.querySelector(".removeEmbedQaBtn").addEventListener("click", () => div.remove());
    qaContainer.appendChild(div);
});

const qaContainer = document.getElementById("qaContainer");
qaContainer.querySelector(".q-input").addEventListener("input", () => checkAllQA());
qaContainer.querySelector(".a-input").addEventListener("input", () => checkAllQA());

const embedContainer = document.getElementById("embedContainer");
embedContainer.querySelector(".embed-q-input").addEventListener("input", () => checkAllQA());
embedContainer.querySelector(".embed-a-input").addEventListener("input", () => checkAllQA());

document.getElementById("submit-all").addEventListener("click", async () => {
    const qaContainer = document.getElementById("qaContainer");
    let qaPairs = []
    Array.from(qaContainer.querySelectorAll(".qa-pair")).forEach((pair) => {
        const q = pair.querySelector(".q-input").value
        const a = pair.querySelector(".a-input").value
        if (q && a) {
            qaPairs.push({
                question: q,
                answer: a
            })
        }
    });
    const embedContainer = document.getElementById("embedContainer");
    let embedPairs = []
    Array.from(embedContainer.querySelectorAll(".embed-pair")).forEach((pair) => {
        const q = pair.querySelector(".embed-q-input").value
        const a = pair.querySelector(".embed-a-input").value
        if (q && a) {
            embedPairs.push({
                question: q,
                answer: a
            })
        }
    });
    const allQAList = document.getElementById("allQAList");
    Array.from(allQAList.querySelectorAll("div")).forEach((pair) => {
        const q = pair.querySelector(".question").value
        const a = pair.querySelector(".answer").value
        if (q && a) {
            embedPairs.push({
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
    if (trans_id === "") {
        const timestamp = Date.now();
        trans_id = collection_name + timestamp
    }
    const fileSummarizeList = []
    finishList.forEach(item => {
        if (item.status === 1 && !item.file.name.endsWith(".ttl")) {
            const textarea = document.getElementById(item.save_file_name)
            if (textarea && textarea.value) {
                fileSummarizeList.push({
                    name: item.save_file_name,
                    value: textarea.value
                })
            }
        }
    })
    const split_length = document.getElementById("splitLength").value
    const response = await fetch("/submit_all_data", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            trans_id: trans_id,
            collection_name: collection_name,
            qa_list: qaPairs,
            embed_list: embedPairs,
            summarize_list: fileSummarizeList,
            split_length: split_length
        }),
    });

    const data = await response.json();

    document.getElementById("submit-text").style.display = "block";

    startAllRequest();
});