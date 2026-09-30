const $ = (id) => document.getElementById(id);

const MAX = 4.5 * 1024 * 1024;
let file = null;

const drop = $("drop");
const input = $("file");
const go = $("go");
const statusEl = $("status");

function setStatus(msg, isError = false, busy = false) {
  statusEl.className = isError ? "error" : "";
  statusEl.innerHTML = busy ? '<span class="spin"></span>' : "";
  statusEl.append(msg);
}

function pick(f) {
  if (!f) return;

  if (f.size > MAX) {
    return setStatus(
      "That file is over 4.5 MB. Choose a smaller one.",
      true
    );
  }

  file = f;

  $("drop-title").textContent = f.name;
  $("drop-hint").textContent =
    (f.size / 1024).toFixed(0) + " KB · click to change";

  go.disabled = false;
  setStatus("");
}

input.addEventListener("change", () => {
  pick(input.files[0]);
});

drop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    input.click();
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  drop.addEventListener(eventName, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  drop.addEventListener(eventName, (e) => {
    e.preventDefault();
    drop.classList.remove("over");
  });
});

drop.addEventListener("drop", (e) => {
  pick(e.dataTransfer.files[0]);
});

async function api(path, body) {
  const res = await fetch(window.API_URL + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }

  return data;
}

function render(text) {
  const box = $("summary");

  box.textContent = "";

  let list = null;

  text.split("\n").forEach((line) => {
    const match = line.match(/^\s*[-*•]\s+(.*)/);

    if (match) {
      if (!list) {
        list = document.createElement("ul");
        box.append(list);
      }

      const li = document.createElement("li");
      li.textContent = match[1].replace(/\*\*/g, "");

      list.append(li);
    } else if (line.trim()) {
      list = null;

      const p = document.createElement("p");
      p.textContent = line.replace(/\*\*/g, "");

      box.append(p);
    }
  });
}

go.addEventListener("click", async () => {
  if (!file) {
    setStatus("Please select a file first.", true);
    return;
  }

  go.disabled = true;
  $("result").hidden = true;

  try {
    // Step 1: Get S3 upload URL
    setStatus("Uploading…", false, true);

    const { uploadUrl, key } = await api("/upload-url", {
      filename: file.name,
    });

    // Step 2: Upload file directly to S3
    const put = await fetch(uploadUrl, {
      method: "PUT",
      body: file,
    });

    if (!put.ok) {
      throw new Error("Upload to S3 failed.");
    }

    // Step 3: Ask Lambda + Bedrock to summarize
    setStatus("Reading and summarizing…", false, true);

    const length = document.querySelector(
      'input[name="length"]:checked'
    ).value;

    const { summary, filename } = await api("/summarize", {
      key,
      length,
    });

    // Step 4: Display summary
    $("result-title").textContent = "Summary of " + filename;

    render(summary);

    $("result").hidden = false;

    setStatus("Done.");
  } catch (err) {
    console.error("Error:", err);

    setStatus(
      err.message || "Something went wrong. Please try again.",
      true
    );
  } finally {
    go.disabled = false;
  }
});

$("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("summary").innerText);

    $("copy").textContent = "Copied";

    setTimeout(() => {
      $("copy").textContent = "Copy summary";
    }, 1500);
  } catch (err) {
    console.error("Copy failed:", err);
  }
});