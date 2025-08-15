const $ = sel => document.querySelector(sel);
const show = el => el.classList.remove('hidden');
const hide = el => el.classList.add('hidden');

const urlInput = $("#url");
const btnNormal = $("#btnNormal");
const btnEdited = $("#btnEdited");
const editor = $("#editor");
const startIn = $("#start");
const endIn = $("#end");
const watermarkIn = $("#watermark");
// Force default watermark text for edited downloads
watermarkIn.value = watermarkIn.value && watermarkIn.value.trim() ? watermarkIn.value : 'Check Bio Link';
const scaleIn = $("#scale");

const result = $("#result");
const fileWrap = $("#fileWrap");
const fileLink = $("#fileLink");
const thumbWrap = $("#thumbWrap");
const thumb = $("#thumb");
const desc = $("#desc");
const copyDesc = $("#copyDesc");
const meta = $("#meta");

btnEdited.addEventListener("click", async () => {
  // First click shows editor; second click starts edited download
  if (editor.classList.contains("hidden")) {
    show(editor);
    return;
  }
  await runDownload("edited");
});

btnNormal.addEventListener("click", async () => {
  hide(editor);
  await runDownload("normal");
});

copyDesc.addEventListener("click", async () => {
  desc.select();
  try {
    await navigator.clipboard.writeText(desc.value);
  } catch (e) {
    // Fallback for older browsers
    document.execCommand("copy");
  }
});

async function runDownload(mode) {
  const url = urlInput.value.trim();
  if (!url) {
    alert("Please paste an Instagram link.");
    return;
  }
  setLoading(true);
  hide(fileWrap);
  hide(thumbWrap);
  hide(result);
  try {
    const payload = { url, mode };
    if (mode === "edited") {
      payload.start = startIn.value;
      payload.end = endIn.value;
      payload.watermark = watermarkIn.value;
      payload.scale = scaleIn.value;
    }
    const res = await fetch("/api/instagram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Failed");
    show(result);
    desc.value = data.description || "";
    if (data.thumbnail) {
      thumb.src = data.thumbnail;
      show(thumbWrap);
    }
    fileLink.href = data.file;
    fileLink.download = data.filename || "download.mp4";
    show(fileWrap);
    meta.textContent = `${data.title ? data.title + " • " : ""}${data.uploader || ""}${data.duration ? " • " + data.duration + "s" : ""}`;
  } catch (e) {
    alert("Error: " + e.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  btnNormal.disabled = isLoading;
  btnEdited.disabled = isLoading;
  btnNormal.textContent = isLoading ? "Processing..." : "Normal Download";
  btnEdited.textContent = isLoading ? "Processing..." : "Edited Download";
}
