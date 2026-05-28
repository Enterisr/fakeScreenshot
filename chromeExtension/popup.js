const photoInput = document.getElementById("photo");
const previewImage = document.getElementById("preview");
const previewEmpty = document.getElementById("previewEmpty");
const uploadButton = document.getElementById("uploadBtn");
const statusText = document.getElementById("status");

const UPLOAD_ENDPOINT = "https://your-server.example/upload";

let selectedFile = null;
let previewUrl = null;

const setStatus = (message, isError = false) => {
  statusText.textContent = message;
  statusText.style.color = isError ? "#b42318" : "#677084";
};

const renderPreview = () => {
  if (!selectedFile) {
    previewImage.style.display = "none";
    previewImage.removeAttribute("src");
    previewEmpty.style.display = "grid";
    return;
  }

  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
  }

  previewUrl = URL.createObjectURL(selectedFile);
  previewImage.src = previewUrl;
  previewImage.style.display = "block";
  previewEmpty.style.display = "none";
};

photoInput.addEventListener("change", () => {
  selectedFile = photoInput.files?.[0] ?? null;
  renderPreview();
  setStatus(
    selectedFile ? `Ready to send ${selectedFile.name}.` : "No file selected.",
  );
});

uploadButton.addEventListener("click", async () => {
  if (!selectedFile) {
    setStatus("Choose a photo before sending.", true);
    return;
  }

  uploadButton.disabled = true;
  setStatus("Uploading photo...");

  try {
    const formData = new FormData();
    formData.append("photo", selectedFile, selectedFile.name);

    const response = await fetch(UPLOAD_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    setStatus("Photo sent successfully.");
  } catch (error) {
    setStatus(`Upload failed: ${error.message}`, true);
  } finally {
    uploadButton.disabled = false;
  }
});
