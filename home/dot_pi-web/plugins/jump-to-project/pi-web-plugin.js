// PI WEB browser plugin: "Jump to project" opens a fuzzy-search dialog over the
// registered projects of the current machine and navigates to the chosen one.

/** Capability that opts our shadow root into the host's shared UI styles. */
const stylesheetIntegration = {
  pluginId: "pi-web",
  id: "stylesheet-integration",
  version: 1,
  parse(value) {
    if (typeof value?.registerRoot !== "function") throw new Error("Stylesheet integration v1 unavailable");
    return value;
  },
};

// Dialog and selection-list styles mirror the host's action palette. They are not
// part of the shared UI bundle. Selectors are prefixed with .surface so they beat
// the shared .ui-button rules, which the host adopts after this <style>.
const STYLE = `
dialog { position: fixed; inset: 0; width: 100%; height: 100%; max-width: none; max-height: none; margin: 0; padding: 0; border: 0; background: transparent; color: var(--pi-text); font: 14px var(--pi-font, system-ui, sans-serif); overflow: hidden; }
dialog::backdrop { background: transparent; }
.backdrop { box-sizing: border-box; width: 100%; height: 100%; display: grid; place-items: start center; padding: min(12dvh, 90px) 16px max(16px, env(safe-area-inset-bottom)); background: var(--pi-overlay); }
.surface { box-sizing: border-box; width: min(720px, calc(100vw - 32px)); max-height: min(640px, calc(100dvh - min(12dvh, 90px) - 16px)); display: flex; flex-direction: column; border: 1px solid var(--pi-border); border-radius: 12px; background: var(--pi-bg); box-shadow: 0 20px 60px var(--pi-shadow-strong); overflow: hidden; }
.surface .ui-dialog-header { display: flex; flex: none; align-items: stretch; min-height: 44px; border-bottom: 1px solid var(--pi-border-muted); }
.surface .ui-dialog-search { box-sizing: border-box; flex: auto; width: 100%; min-width: 0; min-height: 44px; margin: 0; padding: 10px 16px; border: 0; border-radius: 0; background: none; color: var(--pi-text); font: var(--pi-control-font-size, 16px)/1.5 var(--pi-control-font-family, var(--pi-font, system-ui, sans-serif)); }
.surface .ui-dialog-search::placeholder { color: var(--pi-dim); }
.surface .ui-dialog-search:focus-visible { outline: 2px solid var(--pi-accent); outline-offset: -2px; }
.surface .ui-selection-list { flex: auto; min-height: 0; overflow: auto; }
.surface .ui-selection-option { box-sizing: border-box; display: block; width: 100%; min-height: 44px; padding: 10px 16px; color: var(--pi-text); font: 14px/20px var(--pi-font, system-ui, sans-serif); text-align: left; white-space: normal; overflow-wrap: anywhere; box-shadow: inset 0 -1px var(--pi-border-muted); }
.surface .ui-selection-option:hover { background: var(--pi-surface-hover); }
.surface .ui-selection-option.selected, .surface .ui-selection-option.selected:hover { background: var(--pi-selection-bg); }
.surface .ui-selection-detail { display: block; margin-top: 4px; color: var(--pi-muted); font-size: 12px; line-height: 18px; }
.surface .ui-dialog-empty { padding: 24px; color: var(--pi-muted); text-align: center; }
`;

/**
 * Score how well `query` fuzzy-matches `text`: every query character must appear in
 * order. Consecutive matches and matches at a word start score higher.
 * Returns -1 when there is no match.
 */
function fuzzyScore(query, text) {
  const t = text.toLowerCase();
  let score = 0;
  let from = 0;
  let previous = -2;
  for (const char of query) {
    const i = t.indexOf(char, from);
    if (i === -1) return -1;
    score += 1;
    if (i === previous + 1) score += 5;
    if (i === 0 || " /-_.".includes(t[i - 1])) score += 3;
    previous = i;
    from = i + 1;
  }
  return score - t.length * 0.01;
}

/** Filter and sort projects by fuzzy score; the name counts more than the path. */
function rank(projects, query) {
  const q = query.trim().toLowerCase().replace(/\s+/g, "");
  if (q === "") return projects;
  return projects
    .map((project) => {
      const name = fuzzyScore(q, project.name);
      return { project, score: Math.max(name === -1 ? -1 : name + 10, fuzzyScore(q, project.path)) };
    })
    .filter((entry) => entry.score >= 0)
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.project);
}

/**
 * Show the dialog. `onPick(project)` runs on selection; `onClose()` runs once when
 * the dialog goes away for any reason. Returns a function that closes the dialog.
 */
function openDialog(projects, styles, onPick, onClose) {
  const host = document.createElement("div");
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `<style>${STYLE}</style>
    <dialog aria-label="Jump to project">
      <div class="backdrop">
        <section class="surface">
          <header class="ui-dialog-header">
            <input class="ui-dialog-search" aria-label="Search projects" placeholder="Search projects..." autocomplete="off" spellcheck="false">
          </header>
          <div class="ui-selection-list"></div>
        </section>
      </div>
    </dialog>`;
  const dialog = root.querySelector("dialog");
  const backdrop = root.querySelector(".backdrop");
  const input = root.querySelector("input");
  const list = root.querySelector(".ui-selection-list");
  let matches = projects;
  let selected = 0;
  let closed = false;

  const render = () => {
    list.replaceChildren();
    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "ui-dialog-empty";
      empty.textContent = "No matching projects";
      list.append(empty);
      return;
    }
    matches.forEach((project, i) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `ui-button ui-selection-option${i === selected ? " selected" : ""}`;
      button.title = project.path;
      const name = document.createElement("strong");
      name.textContent = project.name;
      const path = document.createElement("small");
      path.className = "ui-selection-detail";
      path.textContent = project.path;
      button.append(name, path);
      button.addEventListener("click", () => pick(project));
      list.append(button);
    });
    list.children[selected]?.scrollIntoView({ block: "nearest" });
  };

  const close = () => {
    if (closed) return;
    closed = true;
    release();
    dialog.close();
    host.remove();
    onClose();
  };
  const pick = (project) => {
    close();
    onPick(project);
  };

  input.addEventListener("input", () => {
    matches = rank(projects, input.value);
    selected = 0;
    render();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (matches.length === 0) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      selected = (selected + step + matches.length) % matches.length;
      render();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (matches[selected]) pick(matches[selected]);
    }
  });
  // Escape fires "cancel" on a modal dialog.
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    close();
  });
  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) close();
  });

  document.body.append(host);
  const release = styles.registerRoot(root, { sharedUi: true });
  render();
  dialog.showModal();
  input.focus();
  return close;
}

export default {
  apiVersion: 5,
  name: "Jump to project",
  requires: [stylesheetIntegration],
  activate({ lifetimeSignal }) {
    let styles;
    let closeDialog;
    const close = () => closeDialog?.();
    lifetimeSignal.addEventListener("abort", close, { once: true });
    return {
      start({ capabilities }) {
        styles = capabilities.resolve(stylesheetIntegration);
      },
      contributions: {
        actions: [{
          id: "project.jump",
          title: "Jump to project",
          description: "Search registered projects and switch to one",
          group: "Navigation",
          shortcut: "mod+alt+o",
          async run(context) {
            if (closeDialog || lifetimeSignal.aborted) return;
            const projects = await context.catalog.projects.list({ signal: lifetimeSignal });
            if (closeDialog || lifetimeSignal.aborted) return;
            closeDialog = openDialog(
              projects,
              styles,
              (project) => context.navigate({ projectId: project.id }, { mode: "patch" }),
              () => { closeDialog = undefined; },
            );
          },
        }],
      },
      dispose() {
        close();
        lifetimeSignal.removeEventListener("abort", close);
      },
    };
  },
};
