// PI WEB browser plugin: "Jump to project" opens a fuzzy-search dialog over the
// registered projects of the current machine and navigates to the chosen one.
// The dialog also lists directories that had a Pi session but are not projects
// yet (from server.js); picking one registers it first.

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

/**
 * Filter and sort projects by fuzzy score; the name counts more than the path.
 * Registered projects (with an `id`) win ties against session directories.
 */
function rank(projects, query) {
  const q = query.trim().toLowerCase().replace(/\s+/g, "");
  if (q === "") return projects;
  return projects
    .map((project) => {
      const name = fuzzyScore(q, project.name);
      const score = Math.max(name === -1 ? -1 : name + 10, fuzzyScore(q, project.path));
      return { project, score: score === -1 || project.id === undefined ? score : score + 1 };
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
      path.textContent = project.id !== undefined
        ? project.path
        : `${project.path} · not a project yet, last session ${project.lastSessionAt.slice(0, 10)}`;
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

/**
 * Ask server.js for directories that had a Pi session, as `{ path, lastSessionAt }`.
 * Returns an empty list when the backend is unavailable, so the dialog still opens.
 */
async function listSessionDirectories(context, signal) {
  try {
    const peer = context.backend?.forScope({ kind: "machine" });
    const result = await peer?.request?.("candidates", null, { signal });
    return Array.isArray(result) ? result : [];
  } catch (error) {
    console.warn("jump-to-project: session directories unavailable", error);
    return [];
  }
}

/**
 * Register `path` as a project on the context's machine, then open it.
 *
 * PRIVATE API: the plugin API has no way to register a project, so this calls
 * the route used by PI WEB's own "Add Project" dialog,
 * `POST api/machines/<machineId>/projects` with `{ path }`. It is not part of the
 * public plugin contract and can change in any PI WEB update. When it fails, fall
 * back to the public `context.addProject()`, which opens the "Add Project" dialog
 * without the path.
 *
 * The host keeps its project list in memory and `context.navigate()` does not
 * reload it, so navigating to the new id shows "project not found". Instead,
 * reload the page on the project's URL (`?project=<id>`, plus `machine=<id>` for
 * a remote machine), which makes the host fetch the project list again.
 */
async function registerProject(context, path) {
  const machineId = context.catalog.machineId;
  let project;
  try {
    const url = new URL(`api/machines/${encodeURIComponent(machineId)}/projects`, document.baseURI);
    const response = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    project = await response.json();
    if (typeof project?.id !== "string") throw new Error("Response has no project id");
  } catch (error) {
    console.warn(`jump-to-project: could not register ${path}`, error);
    await context.addProject();
    return;
  }
  const target = new URL(window.location.pathname, window.location.origin);
  if (machineId !== "local") target.searchParams.set("machine", machineId);
  target.searchParams.set("project", project.id);
  window.location.assign(target);
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
          description: "Search projects and Pi session directories and switch to one",
          group: "Navigation",
          shortcut: "mod+alt+o",
          async run(context) {
            if (closeDialog || lifetimeSignal.aborted) return;
            const [projects, sessionDirs] = await Promise.all([
              context.catalog.projects.list({ signal: lifetimeSignal }),
              listSessionDirectories(context, lifetimeSignal),
            ]);
            if (closeDialog || lifetimeSignal.aborted) return;
            const registered = new Set(projects.map((project) => project.path));
            const candidates = sessionDirs
              .filter((dir) => !registered.has(dir.path))
              .map((dir) => ({ ...dir, name: dir.path.split("/").filter(Boolean).at(-1) ?? dir.path }));
            closeDialog = openDialog(
              [...projects, ...candidates],
              styles,
              (project) => project.id !== undefined
                ? context.navigate({ projectId: project.id }, { mode: "patch" })
                : registerProject(context, project.path),
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
