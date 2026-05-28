(() => {
  const WORKER_URL = chrome.runtime.getURL("worker.js");
  const OBSERVER_ROOT_MARGIN = "300px 0px";
  const OBSERVER_THRESHOLD = 0.05;
  const STYLE_ID = "text-image-classifier-markers";
  const LEGEND_ID = "text-image-classifier-legend";

  const ATTR_SCANNED = "data-text-scan-enqueued";
  const ATTR_RESULT = "data-has-text";
  const ATTR_ERROR = "data-text-scan-error";
  const ATTR_NEWS_TEXT = "data-news-text-detected";

  const CLASS_HAS_NEWS_TEXT = "text-classifier-has-news-text";

  let worker = null;
  let workerReady = false;
  const outboundQueue = [];
  let workerBlobUrl = null;

  let requestCounter = 0;
  const pendingByRequestId = new Map();
  const stats = {
    queued: 0,
    textDetected: 0,
    noText: 0,
    errors: 0,
  };

  let legendQueuedValue = null;
  let legendDetectedValue = null;
  let legendNoTextValue = null;
  let legendErrorValue = null;

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) {
          continue;
        }

        const img = entry.target;
        observer.unobserve(img);
        enqueueImageClassification(img);
      }
    },
    {
      root: null,
      rootMargin: OBSERVER_ROOT_MARGIN,
      threshold: OBSERVER_THRESHOLD,
    },
  );

  function nextRequestId() {
    requestCounter += 1;
    return `img-${Date.now()}-${requestCounter}`;
  }

  function getImageUrl(img) {
    return img.currentSrc || img.src || null;
  }

  function loadImageBytes(imageUrl) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "fetch-image-bytes", imageUrl },
        (response) => {
          const lastError = chrome.runtime.lastError;
          if (lastError) {
            reject(new Error(lastError.message));
            return;
          }

          if (!response || !response.ok) {
            reject(new Error(response?.error || "failed-to-fetch-image-bytes"));
            return;
          }

          resolve({ bytes: response.bytes, mimeType: response.mimeType });
        },
      );
    });
  }

  function updateLegend() {
    if (!legendQueuedValue) {
      return;
    }

    legendQueuedValue.textContent = String(stats.queued);
    legendDetectedValue.textContent = String(stats.textDetected);
    legendNoTextValue.textContent = String(stats.noText);
    legendErrorValue.textContent = String(stats.errors);
  }

  async function enqueueImageClassification(img) {
    if (!(img instanceof HTMLImageElement)) {
      return;
    }

    if (img.getAttribute(ATTR_SCANNED) === "1") {
      return;
    }

    const imageUrl = getImageUrl(img);
    if (!imageUrl) {
      return;
    }

    const requestId = nextRequestId();
    pendingByRequestId.set(requestId, img);

    stats.queued += 1;
    updateLegend();

    img.setAttribute(ATTR_SCANNED, "1");

    try {
      const imagePayload = await loadImageBytes(imageUrl);
      postToWorker({
        type: "classify-image-bytes",
        requestId,
        imageUrl,
        imageBytes: imagePayload.bytes,
        imageMimeType: imagePayload.mimeType,
      });
    } catch (error) {
      pendingByRequestId.delete(requestId);
      img.setAttribute(ATTR_RESULT, "false");
      img.setAttribute(
        ATTR_ERROR,
        error instanceof Error ? error.message : String(error),
      );
      applyResultMarkup(img, false, true);
      stats.errors += 1;
      updateLegend();
    }
  }

  function postToWorker(message) {
    if (workerReady && worker) {
      if (message?.imageBytes instanceof ArrayBuffer) {
        worker.postMessage(message, [message.imageBytes]);
      } else {
        worker.postMessage(message);
      }
      return;
    }

    outboundQueue.push(message);
  }

  function loadWorkerSource() {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "get-worker-source" }, (response) => {
        const lastError = chrome.runtime.lastError;
        if (lastError) {
          reject(new Error(lastError.message));
          return;
        }

        if (!response || !response.ok) {
          reject(new Error(response?.error || "failed-to-load-worker-source"));
          return;
        }

        resolve(response.source);
      });
    });
  }

  async function createWorker() {
    const source = await loadWorkerSource();
    const blobUrl = URL.createObjectURL(
      new Blob([source], { type: "text/javascript" }),
    );

    workerBlobUrl = blobUrl;
    return new Worker(blobUrl);
  }

  function observeImage(img) {
    if (!(img instanceof HTMLImageElement)) {
      return;
    }

    if (!img.isConnected) {
      return;
    }

    if (img.getAttribute(ATTR_SCANNED) === "1") {
      return;
    }

    observer.observe(img);
  }

  function observeAllImages(root = document) {
    root.querySelectorAll("img").forEach((img) => observeImage(img));
  }

  function ensureMarkerStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      img.${CLASS_HAS_NEWS_TEXT} {
        outline: 3px solid #d7263d;
        outline-offset: 2px;
        box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.85), 0 0 0 6px rgba(215, 38, 61, 0.26);
      }

      #${LEGEND_ID} {
        position: fixed;
        right: 12px;
        bottom: 12px;
        z-index: 2147483647;
        width: 240px;
        border-radius: 10px;
        border: 1px solid rgba(28, 31, 38, 0.26);
        background: rgba(255, 255, 255, 0.95);
        color: #1f2430;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.16);
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        font-size: 12px;
        line-height: 1.35;
        backdrop-filter: blur(4px);
        pointer-events: none;
      }

      #${LEGEND_ID} .legend-head {
        padding: 10px 12px 8px;
        font-weight: 700;
        border-bottom: 1px solid rgba(28, 31, 38, 0.14);
      }

      #${LEGEND_ID} .legend-body {
        padding: 8px 12px 10px;
      }

      #${LEGEND_ID} .legend-row {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 10px;
        margin: 4px 0;
      }

      #${LEGEND_ID} .legend-row .k {
        color: #4a5261;
      }

      #${LEGEND_ID} .legend-row .v {
        font-weight: 700;
      }

      #${LEGEND_ID} .legend-row.detected .v {
        color: #b21a2f;
      }

      #${LEGEND_ID} .legend-row.ok .v {
        color: #0e6f46;
      }

      #${LEGEND_ID} .legend-row.err .v {
        color: #9d4117;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureLegend() {
    if (document.getElementById(LEGEND_ID)) {
      return;
    }

    const legend = document.createElement("section");
    legend.id = LEGEND_ID;
    legend.setAttribute("aria-label", "Image text classifier status");

    const head = document.createElement("div");
    head.className = "legend-head";
    head.textContent = "Image Text Classifier";

    const body = document.createElement("div");
    body.className = "legend-body";

    const makeRow = (label, className) => {
      const row = document.createElement("div");
      row.className = `legend-row ${className}`;

      const key = document.createElement("span");
      key.className = "k";
      key.textContent = label;

      const value = document.createElement("span");
      value.className = "v";
      value.textContent = "0";

      row.appendChild(key);
      row.appendChild(value);
      body.appendChild(row);
      return value;
    };

    legendQueuedValue = makeRow("Queued", "all");
    legendDetectedValue = makeRow("News-like text", "detected");
    legendNoTextValue = makeRow("No text", "ok");
    legendErrorValue = makeRow("Errors", "err");

    legend.appendChild(head);
    legend.appendChild(body);
    document.documentElement.appendChild(legend);

    updateLegend();
  }

  function applyResultMarkup(img, hasText, hasError = false) {
    img.setAttribute(ATTR_NEWS_TEXT, hasText ? "true" : "false");

    if (hasError) {
      img.classList.remove(CLASS_HAS_NEWS_TEXT);
      img.title = "Text classifier: failed";
      return;
    }

    if (hasText) {
      img.classList.add(CLASS_HAS_NEWS_TEXT);
      img.title = "Text classifier: news-like text detected";
    } else {
      img.classList.remove(CLASS_HAS_NEWS_TEXT);
      img.title = "Text classifier: no news-like text detected";
    }
  }

  function failPendingRequests(reason) {
    for (const [, img] of pendingByRequestId.entries()) {
      if (!img || !img.isConnected) {
        continue;
      }

      img.setAttribute(ATTR_RESULT, "false");
      img.setAttribute(ATTR_ERROR, reason);
      applyResultMarkup(img, false, true);
      stats.errors += 1;
    }

    pendingByRequestId.clear();
    updateLegend();
  }

  function attachWorkerListeners(targetWorker) {
    targetWorker.addEventListener("message", (event) => {
      const data = event.data;
      if (!data || data.type !== "classification-result") {
        return;
      }

      const img = pendingByRequestId.get(data.requestId);
      pendingByRequestId.delete(data.requestId);

      if (!img || !img.isConnected) {
        return;
      }

      if (data.ok) {
        const hasText = Boolean(data.hasText);
        img.setAttribute(ATTR_RESULT, String(hasText));
        img.removeAttribute(ATTR_ERROR);
        applyResultMarkup(img, hasText, false);

        if (hasText) {
          stats.textDetected += 1;
        } else {
          stats.noText += 1;
        }
      } else {
        img.setAttribute(ATTR_RESULT, "false");
        img.setAttribute(ATTR_ERROR, data.error || "classification-failed");
        applyResultMarkup(img, false, true);
        stats.errors += 1;
      }

      updateLegend();
    });

    targetWorker.addEventListener("error", (errorEvent) => {
      console.warn(
        "[TextImageClassifier] Worker runtime error:",
        errorEvent.message,
      );
      failPendingRequests(errorEvent.message || "worker-runtime-error");
    });

    targetWorker.addEventListener("messageerror", () => {
      failPendingRequests("worker-message-error");
    });
  }

  async function initializeWorker() {
    try {
      worker = await createWorker();
      attachWorkerListeners(worker);
      workerReady = true;

      while (outboundQueue.length > 0) {
        worker.postMessage(outboundQueue.shift());
      }
    } catch (error) {
      const reason =
        error instanceof Error ? error.message : "worker-initialization-failed";
      console.warn(
        "[TextImageClassifier] Worker initialization failed:",
        reason,
      );
      failPendingRequests(reason);
    }
  }

  window.addEventListener("unload", () => {
    if (worker) {
      worker.terminate();
    }

    if (workerBlobUrl) {
      URL.revokeObjectURL(workerBlobUrl);
      workerBlobUrl = null;
    }
  });

  const mutationObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) {
          continue;
        }

        if (node.tagName === "IMG") {
          observeImage(node);
        }

        observeAllImages(node);
      }
    }
  });

  ensureMarkerStyles();
  ensureLegend();
  void initializeWorker();
  observeAllImages(document);
  mutationObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
