chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "get-worker-source") {
    if (!message || message.type !== "fetch-image-bytes") {
      return false;
    }

    (async () => {
      const response = await fetch(message.imageUrl, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Failed to fetch image: ${response.status}`);
      }

      const blob = await response.blob();
      const bytes = await blob.arrayBuffer();
      return {
        bytes,
        mimeType: blob.type || response.headers.get("content-type") || "image/*",
      };
    })()
      .then((result) =>
        sendResponse({
          ok: true,
          bytes: result.bytes,
          mimeType: result.mimeType,
        }),
      )
      .catch((error) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        }),
      );

    return true;
  }

  (async () => {
    const response = await fetch(chrome.runtime.getURL("worker.js"));
    if (!response.ok) {
      throw new Error(`Failed to load worker.js: ${response.status}`);
    }

    return response.text();
  })()
    .then((source) => sendResponse({ ok: true, source }))
    .catch((error) =>
      sendResponse({
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      }),
    );

  return true;
});
