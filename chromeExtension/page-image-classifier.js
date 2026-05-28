(() => {
  const TAG_ATTRIBUTE = "data-news-image-prediction";
  const MODEL_NAME = "local-news-image-placeholder-v1";

  const collectImageFeatures = (img) => {
    const src = (img.currentSrc || img.src || "").toLowerCase();
    const alt = (img.alt || "").toLowerCase();
    const className = (img.className || "").toString().toLowerCase();
    const width = img.naturalWidth || img.width || 0;
    const height = img.naturalHeight || img.height || 0;

    return {
      src,
      alt,
      className,
      width,
      height,
      area: width * height,
      aspectRatio: height > 0 ? width / height : 0,
    };
  };

  const predictNewsImage = (features) => {
    // Placeholder local model. Replace this function with a real local model call.
    let score = 0.2;

    const combinedText = `${features.src} ${features.alt} ${features.className}`;

    if (/news|article|headline|report|press|editorial/.test(combinedText)) {
      score += 0.45;
    }

    if (/hero|cover|lead|feature/.test(combinedText)) {
      score += 0.2;
    }

    if (features.area > 200000) {
      score += 0.15;
    }

    if (features.aspectRatio > 1.2 && features.aspectRatio < 2.2) {
      score += 0.1;
    }

    const normalizedScore = Math.max(0, Math.min(1, score));
    return {
      model: MODEL_NAME,
      score: normalizedScore,
      isNewsImage: normalizedScore >= 0.6,
    };
  };

  const classifyImage = (img) => {
    if (!(img instanceof HTMLImageElement)) {
      return;
    }

    if (img.getAttribute(TAG_ATTRIBUTE)) {
      return;
    }

    const features = collectImageFeatures(img);
    const prediction = predictNewsImage(features);

    img.setAttribute(
      TAG_ATTRIBUTE,
      prediction.isNewsImage ? "news" : "not-news",
    );
    img.setAttribute("data-news-image-score", prediction.score.toFixed(2));

    // Keep logs compact and useful while this is still a placeholder model.
    console.debug("[ImageClassifier]", {
      src: img.currentSrc || img.src,
      alt: img.alt,
      prediction,
    });
  };

  const classifyAllImages = () => {
    document.querySelectorAll("img").forEach((img) => {
      if (img.complete) {
        classifyImage(img);
      } else {
        img.addEventListener("load", () => classifyImage(img), { once: true });
      }
    });
  };

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof Element)) {
          continue;
        }

        if (node.tagName === "IMG") {
          classifyImage(node);
        }

        node.querySelectorAll?.("img").forEach((img) => classifyImage(img));
      }
    }
  });

  classifyAllImages();
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
