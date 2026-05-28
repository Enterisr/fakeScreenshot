# Photo Uploader Chrome Extension

This is a simple Chrome extension that lets you:

1. Pick a photo from the popup.
2. Preview it locally.
3. Upload it to an external server with a `POST` request.
4. Classify every page `<img>` as `news` or `not-news` with a local placeholder model.

## Install locally

1. Open `chrome://extensions`.
2. Turn on Developer mode.
3. Click Load unpacked.
4. Select this folder.

## How it works

- Choose an image file.
- Click Send photo.
- On every visited page, a content script scans all `<img>` elements and writes prediction tags:
  - `data-news-image-prediction="news|not-news"`
  - `data-news-image-score="0.00-1.00"`

The extension sends the file as `multipart/form-data` under the field name `photo`.
The upload endpoint is configured in `popup.js` via the `UPLOAD_ENDPOINT` constant.

The image classification currently uses a heuristic placeholder in `page-image-classifier.js`.
It runs locally in the browser context and does not train or download a model yet.

## Notes

- No server is included here.
- Update `UPLOAD_ENDPOINT` in `popup.js` to point at your server.

## Demo page for classifier

- Open `demo.html` through a local HTTP server (for example `python -m http.server 8080`).
- Visit `http://localhost:8080/demo.html` with the extension enabled.
- Scroll the page to trigger lazy scanning through `IntersectionObserver`.
- Images marked as text/news-like are highlighted with a red outline by the content script.
