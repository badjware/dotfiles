// Loads chromium from patchright, falling back to playwright.
function load() {
  try {
    return require("patchright");
  } catch (e) {
    if (e.code !== "MODULE_NOT_FOUND") throw e;
  }
  try {
    return require("playwright");
  } catch (e) {
    if (e.code !== "MODULE_NOT_FOUND") throw e;
    throw new Error("Neither 'patchright' nor 'playwright' is installed. Install one: npm i -g patchright");
  }
}

module.exports = load();
