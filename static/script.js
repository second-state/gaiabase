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


// Upload Files
document.getElementById("fileInput").addEventListener("change", async (e) => {
    const fileListPlace = document.getElementById("fileList");
    const formData = new FormData();

    console.log(e.target.files)

    fileList.push(...e.target.files)

    fileListPlace.innerHTML = ""; // Clear previous list
    finishList.forEach((file) => {
        const li = document.createElement("li");
        li.textContent = file.name;
        fileListPlace.appendChild(li);
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
    finishList.push(...fileList)
    fileList = []
    fileListPlace.innerHTML = ""; // Clear previous list
    finishList.forEach((file) => {
        const li = document.createElement("li");
        li.textContent = file.name;
        fileListPlace.appendChild(li);
    });
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