// PI WEB browser plugin: when the navigation sidebar is collapsed on desktop, the
// bar above the chat holds only the expand button. This fills it with the current
// "project / workspace".
//
// The plugin API has no slot for that bar, so this reaches into host internals:
// pi-web-app's shadow root -> <app-mobile-main-tabs> -> .mobile-tabs-frame.controls-only.
// A host update that renames these breaks the label silently, not the app.

const LABEL_STYLE = [
  "flex: 1 1 auto",
  "min-width: 0",
  "align-self: center",
  "padding: 0 12px",
  "overflow: hidden",
  "white-space: nowrap",
  "text-overflow: ellipsis",
  "color: var(--pi-muted)",
  "font: 13px var(--pi-font, system-ui, sans-serif)",
].join("; ");

export default {
  apiVersion: 5,
  name: "Collapsed sidebar context",
  activate({ selection, lifetimeSignal }) {
    const app = document.querySelector("pi-web-app");
    if (!selection || !app?.shadowRoot) {
      console.warn("collapsed-context: selection API or pi-web-app shadow root unavailable");
      return { contributions: {} };
    }

    const label = document.createElement("div");
    label.style.cssText = LABEL_STYLE;
    let tabs;
    const tabsObserver = new MutationObserver(() => sync());

    /** Place, update, or remove the label to match the host bar and selection. */
    function sync() {
      const current = app.shadowRoot.querySelector("app-mobile-main-tabs");
      if (current !== tabs) {
        tabs = current;
        tabsObserver.disconnect();
        if (tabs?.shadowRoot) {
          tabsObserver.observe(tabs.shadowRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
        }
      }
      const frame = tabs?.shadowRoot?.querySelector(".mobile-tabs-frame.controls-only");
      const { selectedProject: project, selectedWorkspace: workspace } = selection.getSnapshot();
      if (!frame || !project) {
        label.remove();
        return;
      }
      const text = workspace ? `${project.name} / ${workspace.label}` : project.name;
      const title = workspace?.path ?? project.path;
      if (label.textContent !== text) label.textContent = text;
      if (label.title !== title) label.title = title;
      const anchor = frame.querySelector(".mobile-tabs");
      if (label.parentNode !== frame || label.nextSibling !== anchor) frame.insertBefore(label, anchor);
    }

    const appObserver = new MutationObserver(() => sync());
    appObserver.observe(app.shadowRoot, { childList: true, subtree: true });
    const unsubscribe = selection.subscribe(() => sync());
    sync();

    const stop = () => {
      unsubscribe();
      appObserver.disconnect();
      tabsObserver.disconnect();
      label.remove();
    };
    lifetimeSignal.addEventListener("abort", stop, { once: true });
    return { contributions: {}, dispose: stop };
  },
};
