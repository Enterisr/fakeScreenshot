/* global OffscreenCanvas, createImageBitmap */

const MAX_PARALLEL_TASKS = 2;
const IMAGE_SIZE = 224;
const MODEL_CANDIDATES = [
  "Xenova/resnet-50-document-classifier",
  "Xenova/mobilenetv3-small-100",
];

const TEXT_LABEL_PATTERNS = [
  /document/i,
  /text/i,
  /newspaper/i,
  /book/i,
  /magazine/i,
  /screenshot/i,
  /whiteboard/i,
  /receipt/i,
  /form/i,
  /letter/i,
  /invoice/i,
];

const DEBUG = true;

function debugLog(stage, details = undefined) {
  if (!DEBUG) {
    return;
  }

  if (typeof details === "undefined") {
    console.debug(`[ImageTextWorker] ${stage}`);
    return;
  }

  console.debug(`[ImageTextWorker] ${stage}`, details);
}

function debugWarn(stage, details = undefined) {
  if (!DEBUG) {
    return;
  }

  if (typeof details === "undefined") {
    console.warn(`[ImageTextWorker] ${stage}`);
    return;
  }

  console.warn(`[ImageTextWorker] ${stage}`, details);
}

let classifierPromise = null;
let modelIdInUse = null;
let transformersRuntimePromise = null;
let transformersPipeline = null;
let transformersRawImage = null;

const queue = [];
let activeCount = 0;

debugLog("worker-script-loaded", {
  maxParallelTasks: MAX_PARALLEL_TASKS,
  imageSize: IMAGE_SIZE,
  modelCandidates: MODEL_CANDIDATES,
});

function resolveImageUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string") {
    debugWarn("resolve-image-url:invalid-input", { rawUrl });
    return null;
  }

  try {
    // Support protocol-relative URLs.
    if (rawUrl.startsWith("//")) {
      const resolved = `https:${rawUrl}`;
      debugLog("resolve-image-url:protocol-relative", { rawUrl, resolved });
      return resolved;
    }

    const parsed = new URL(rawUrl, "https://example.invalid");
    if (
      parsed.protocol === "http:" ||
      parsed.protocol === "https:" ||
      parsed.protocol === "file:"
    ) {
      debugLog("resolve-image-url:resolved", { rawUrl, resolved: parsed.href });
      return parsed.href;
    }

    debugWarn("resolve-image-url:unsupported-protocol", {
      rawUrl,
      protocol: parsed.protocol,
    });
    return null;
  } catch {
    debugWarn("resolve-image-url:parse-failed", { rawUrl });
    return null;
  }
}

async function loadTransformersRuntime() {
  if (transformersRuntimePromise) {
    debugLog("transformers-runtime:reuse-promise");
    return transformersRuntimePromise;
  }

  debugLog("transformers-runtime:loading-start");
  transformersRuntimePromise = (async () => {
    try {
      const mod = await import("@huggingface/transformers");
      debugLog("transformers-runtime:loaded", {
        exportedKeys: Object.keys(mod).slice(0, 12),
      });
      mod.env.useBrowserCache = true;
      mod.env.allowLocalModels = false;
      transformersPipeline = mod.pipeline;
      transformersRawImage = mod.RawImage;
      debugLog("transformers-runtime:configured", {
        useBrowserCache: mod.env.useBrowserCache,
        allowLocalModels: mod.env.allowLocalModels,
      });
      return true;
    } catch (error) {
      debugWarn(
        "[ImageTextWorker] Transformers runtime unavailable, using fallback classifier.",
        String(error),
      );
      return false;
    }
  })();

  return transformersRuntimePromise;
}

async function initializeClassifier() {
  if (classifierPromise) {
    debugLog("classifier:init-reuse");
    return classifierPromise;
  }

  debugLog("classifier:init-start");
  classifierPromise = (async () => {
    const hasTransformers = await loadTransformersRuntime();
    debugLog("classifier:runtime-status", {
      hasTransformers,
      pipelineAvailable: Boolean(transformersPipeline),
      rawImageAvailable: Boolean(transformersRawImage),
    });
    if (!hasTransformers || !transformersPipeline) {
      modelIdInUse = "heuristic-fallback-v1";
      debugWarn("classifier:fallback-selected", { modelIdInUse });
      return null;
    }

    let lastError;
    for (const modelId of MODEL_CANDIDATES) {
      try {
        debugLog("classifier:model-load-attempt", { modelId });
        const model = await transformersPipeline(
          "image-classification",
          modelId,
          {
            dtype: "q8",
            device: "wasm",
          },
        );
        modelIdInUse = modelId;
        debugLog("classifier:model-load-success", { modelIdInUse });
        return model;
      } catch (error) {
        lastError = error;
        debugWarn("classifier:model-load-failed", {
          modelId,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    debugWarn(
      "[ImageTextWorker] Failed to load model candidates, using fallback classifier.",
      String(lastError),
    );
    modelIdInUse = "heuristic-fallback-v1";
    debugWarn("classifier:fallback-selected", { modelIdInUse });
    return null;
  })();

  return classifierPromise;
}

async function imageBitmapToRawImage(imageBitmap) {
  debugLog("preprocess:raw-image-start", {
    width: imageBitmap.width,
    height: imageBitmap.height,
    targetSize: IMAGE_SIZE,
  });
  const canvas = new OffscreenCanvas(IMAGE_SIZE, IMAGE_SIZE);
  const context = canvas.getContext("2d", {
    alpha: false,
    willReadFrequently: true,
  });

  if (!context) {
    throw new Error("2D context is unavailable in worker.");
  }

  context.drawImage(imageBitmap, 0, 0, IMAGE_SIZE, IMAGE_SIZE);
  const imageData = context.getImageData(0, 0, IMAGE_SIZE, IMAGE_SIZE);
  if (!transformersRawImage) {
    throw new Error("RawImage runtime is not available.");
  }

  debugLog("preprocess:raw-image-ready", {
    byteLength: imageData.data.byteLength,
  });
  return transformersRawImage.fromImageData(imageData);
}

function fallbackHasTextFromBitmap(imageBitmap) {
  debugLog("fallback:analyze-start", {
    width: imageBitmap.width,
    height: imageBitmap.height,
  });
  const canvas = new OffscreenCanvas(IMAGE_SIZE, IMAGE_SIZE);
  const context = canvas.getContext("2d", {
    alpha: false,
    willReadFrequently: true,
  });

  if (!context) {
    return false;
  }

  context.drawImage(imageBitmap, 0, 0, IMAGE_SIZE, IMAGE_SIZE);
  const { data, width, height } = context.getImageData(
    0,
    0,
    IMAGE_SIZE,
    IMAGE_SIZE,
  );

  const luminance = new Float32Array(width * height);
  let brightCount = 0;
  let lowSaturationCount = 0;

  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const sat = max === 0 ? 0 : (max - min) / max;
    const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;

    luminance[p] = y;
    if (y > 175) {
      brightCount += 1;
    }
    if (sat < 0.18) {
      lowSaturationCount += 1;
    }
  }

  let edgeCount = 0;
  for (let y = 0; y < height - 1; y += 1) {
    for (let x = 0; x < width - 1; x += 1) {
      const idx = y * width + x;
      const dx = Math.abs(luminance[idx] - luminance[idx + 1]);
      const dy = Math.abs(luminance[idx] - luminance[idx + width]);

      if (dx > 34) {
        edgeCount += 1;
      }
      if (dy > 34) {
        edgeCount += 1;
      }
    }
  }

  const pixelCount = width * height;
  const edgeRatio = edgeCount / (pixelCount * 2);
  const brightRatio = brightCount / pixelCount;
  const lowSaturationRatio = lowSaturationCount / pixelCount;
  const decision =
    (edgeRatio > 0.2 && brightRatio > 0.33) ||
    (edgeRatio > 0.24 && lowSaturationRatio > 0.48);

  debugLog("fallback:analyze-complete", {
    pixelCount,
    edgeCount,
    edgeRatio: Number(edgeRatio.toFixed(4)),
    brightRatio: Number(brightRatio.toFixed(4)),
    lowSaturationRatio: Number(lowSaturationRatio.toFixed(4)),
    decision,
  });

  return decision;
}

function hasTextFromPredictions(predictions) {
  if (!Array.isArray(predictions)) {
    debugWarn("classifier:predictions-not-array", { predictions });
    return false;
  }

  let textScore = 0;
  let nonTextScore = 0;

  for (const pred of predictions) {
    const label = String(pred?.label ?? "");
    const score = Number(pred?.score ?? 0);

    if (TEXT_LABEL_PATTERNS.some((pattern) => pattern.test(label))) {
      textScore += score;
    } else {
      nonTextScore += score;
    }
  }

  const decision = textScore >= Math.max(nonTextScore, 0.35);
  debugLog("classifier:prediction-analysis", {
    textScore: Number(textScore.toFixed(4)),
    nonTextScore: Number(nonTextScore.toFixed(4)),
    decision,
    topPredictions: predictions.slice(0, 5),
  });
  return decision;
}

async function classifyImageUrl(imageUrl) {
  const startedAt = performance.now();
  const resolvedUrl = resolveImageUrl(imageUrl);
  if (!resolvedUrl) {
    debugWarn("classify:invalid-url", { imageUrl });
    return false;
  }

  debugLog("classify:start", { imageUrl, resolvedUrl });

  const response = await fetch(resolvedUrl, {
    method: "GET",
    credentials: "omit",
    cache: "force-cache",
  });

  debugLog("classify:fetched-response", {
    url: resolvedUrl,
    ok: response.ok,
    status: response.status,
    contentType: response.headers.get("content-type"),
    contentLength: response.headers.get("content-length"),
    elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
  });

  if (!response.ok) {
    throw new Error(`Image fetch failed with status ${response.status}`);
  }

  const blob = await response.blob();
  debugLog("classify:blob-ready", {
    size: blob.size,
    type: blob.type,
  });
  const imageBitmap = await createImageBitmap(blob);

  debugLog("classify:image-bitmap-ready", {
    width: imageBitmap.width,
    height: imageBitmap.height,
  });

  try {
    const classifier = await initializeClassifier();
    if (!classifier) {
      const fallbackDecision = fallbackHasTextFromBitmap(imageBitmap);
      debugLog("classify:fallback-result", {
        decision: fallbackDecision,
        elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
      });
      return fallbackDecision;
    }

    const input = await imageBitmapToRawImage(imageBitmap);
    debugLog("classify:model-input-ready", {
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
    });
    const predictions = await classifier(input, { top_k: 5 });
    const decision = hasTextFromPredictions(predictions);
    debugLog("classify:model-result", {
      decision,
      predictions,
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
      modelIdInUse,
    });
    return decision;
  } finally {
    debugLog("classify:image-bitmap-release", { resolvedUrl });
    imageBitmap.close();
  }
}

async function classifyImageBytes(imageBytes, imageMimeType, imageUrl = null) {
  const startedAt = performance.now();
  const byteLength = imageBytes?.byteLength ?? imageBytes?.length ?? 0;
  debugLog("classify-bytes:start", {
    imageUrl,
    imageMimeType,
    byteLength,
  });

  if (!imageBytes) {
    debugWarn("classify-bytes:missing-bytes", { imageUrl, imageMimeType });
    return false;
  }

  const typedBytes =
    imageBytes instanceof ArrayBuffer ? new Uint8Array(imageBytes) : new Uint8Array(imageBytes);
  const blob = new Blob([typedBytes], {
    type: imageMimeType || "image/*",
  });

  debugLog("classify-bytes:blob-ready", {
    size: blob.size,
    type: blob.type,
  });

  const imageBitmap = await createImageBitmap(blob);

  debugLog("classify-bytes:image-bitmap-ready", {
    width: imageBitmap.width,
    height: imageBitmap.height,
  });

  try {
    const classifier = await initializeClassifier();
    if (!classifier) {
      const fallbackDecision = fallbackHasTextFromBitmap(imageBitmap);
      debugLog("classify-bytes:fallback-result", {
        decision: fallbackDecision,
        elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
      });
      return fallbackDecision;
    }

    const input = await imageBitmapToRawImage(imageBitmap);
    debugLog("classify-bytes:model-input-ready", {
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
    });
    const predictions = await classifier(input, { top_k: 5 });
    const decision = hasTextFromPredictions(predictions);
    debugLog("classify-bytes:model-result", {
      decision,
      predictions,
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
      modelIdInUse,
    });
    return decision;
  } finally {
    debugLog("classify-bytes:image-bitmap-release", { imageUrl });
    imageBitmap.close();
  }
}

function postResult(job, payload) {
  debugLog("result:post", {
    requestId: job.requestId,
    imageUrl: job.imageUrl,
    payload,
    modelIdInUse,
    queueLength: queue.length,
    activeCount,
  });
  self.postMessage({
    type: "classification-result",
    requestId: job.requestId,
    imageUrl: job.imageUrl,
    ...payload,
    modelId: modelIdInUse,
  });
}

async function runJob(job) {
  const startedAt = performance.now();
  debugLog("job:start", {
    requestId: job.requestId,
    imageUrl: job.imageUrl,
    messageType: job.messageType,
    activeCount,
    queueLength: queue.length,
  });
  try {
    const hasText =
      job.messageType === "classify-image-bytes"
        ? await classifyImageBytes(job.imageBytes, job.imageMimeType, job.imageUrl)
        : await classifyImageUrl(job.imageUrl);
    debugLog("job:complete", {
      requestId: job.requestId,
      hasText,
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
    });
    postResult(job, { ok: true, hasText });
  } catch (error) {
    debugWarn("job:error", {
      requestId: job.requestId,
      error: error instanceof Error ? error.message : String(error),
      elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
    });
    postResult(job, {
      ok: false,
      hasText: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

function pumpQueue() {
  debugLog("queue:pump", {
    activeCount,
    queueLength: queue.length,
    maxParallel: MAX_PARALLEL_TASKS,
  });
  while (activeCount < MAX_PARALLEL_TASKS && queue.length > 0) {
    const job = queue.shift();
    activeCount += 1;
    debugLog("queue:dequeue", {
      requestId: job.requestId,
      imageUrl: job.imageUrl,
      activeCount,
      queueLength: queue.length,
    });

    runJob(job)
      .catch(() => {
        // Errors are already posted in runJob.
      })
      .finally(() => {
        activeCount -= 1;
        debugLog("queue:job-settled", {
          requestId: job.requestId,
          activeCount,
          queueLength: queue.length,
        });
        pumpQueue();
      });
  }
}

self.addEventListener("message", (event) => {
  const data = event.data;
  if (
    !data ||
    (data.type !== "classify-image" && data.type !== "classify-image-bytes")
  ) {
    debugLog("message:ignored", { data });
    return;
  }

  debugLog("message:received", {
    requestId: data.requestId,
    imageUrl: data.imageUrl,
    messageType: data.type,
    queueLengthBefore: queue.length,
    activeCount,
  });

  queue.push({
    requestId: data.requestId,
    imageUrl: data.imageUrl,
    imageBytes: data.imageBytes,
    imageMimeType: data.imageMimeType,
    messageType: data.type,
  });

  debugLog("message:enqueued", {
    requestId: data.requestId,
    queueLengthAfter: queue.length,
  });

  pumpQueue();
});
