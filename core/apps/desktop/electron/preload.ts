import { contextBridge, ipcRenderer, webUtils } from 'electron'

contextBridge.exposeInMainWorld('athenaDesktop', {
  getConnection: profile => ipcRenderer.invoke('athena:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('athena:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('athena:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('athena:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('athena:window:openSession', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('athena:window:openInstance'),
  claimAmbientCue: key => ipcRenderer.invoke('athena:ambient:claim', key),
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('athena:wake-indicator:get'),
    setState: state => ipcRenderer.send('athena:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('athena:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('athena:wake-indicator:state', listener)
    }
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('athena:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('athena:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('athena:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('athena:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('athena:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('athena:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('athena:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('athena:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('athena:pet-overlay:control', listener)
    }
  },
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('athena:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('athena:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('athena:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('athena:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('athena:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('athena:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('athena:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('athena:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('athena:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('athena:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('athena:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('athena:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('athena:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('athena:connection-config:test', payload),
  sshConfigHosts: () => ipcRenderer.invoke('athena:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('athena:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('athena:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('athena:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('athena:connection-config:oauth-logout', remoteUrl),
  // Athena Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('athena:cloud:status'),
    login: () => ipcRenderer.invoke('athena:cloud:login'),
    logout: () => ipcRenderer.invoke('athena:cloud:logout'),
    discover: org => ipcRenderer.invoke('athena:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('athena:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('athena:profile:get'),
    set: name => ipcRenderer.invoke('athena:profile:set', name)
  },
  api: request => ipcRenderer.invoke('athena:api', request),
  notify: payload => ipcRenderer.invoke('athena:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('athena:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('athena:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('athena:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('athena:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('athena:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('athena:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('athena:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('athena:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('athena:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('athena:readClipboard'),
  saveImageFromUrl: url => ipcRenderer.invoke('athena:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('athena:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('athena:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('athena:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('athena:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('athena:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('athena:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('athena:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('athena:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('athena:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('athena:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('athena:keep-awake', on),
  setPreviewShortcutActive: active => ipcRenderer.send('athena:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('athena:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('athena:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('athena:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('athena:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('athena:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('athena:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('athena:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('athena:zoom:get'),
    setPercent: percent => ipcRenderer.send('athena:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:zoom:changed', listener)

      return () => ipcRenderer.removeListener('athena:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('athena:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('athena:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('athena:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('athena:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('athena:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('athena:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('athena:fs:desktopPluginsRoot'),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('athena:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('athena:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('athena:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('athena:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('athena:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('athena:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('athena:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('athena:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('athena:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('athena:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('athena:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('athena:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('athena:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('athena:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('athena:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('athena:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('athena:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('athena:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('athena:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('athena:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('athena:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('athena:git:review:shipInfo', repoPath),
      createPr: repoPath => ipcRenderer.invoke('athena:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('athena:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('athena:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('athena:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('athena:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('athena:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `athena:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `athena:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('athena:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('athena:close-preview-requested', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('athena:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('athena:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('athena:open-updates', listener)

    return () => ipcRenderer.removeListener('athena:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:deep-link', listener)

    return () => ipcRenderer.removeListener('athena:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('athena:deep-link-ready'),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:window-state-changed', listener)

    return () => ipcRenderer.removeListener('athena:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('athena:focus-session', listener)

    return () => ipcRenderer.removeListener('athena:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:notification-action', listener)

    return () => ipcRenderer.removeListener('athena:notification-action', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('athena:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:backend-exit', listener)

    return () => ipcRenderer.removeListener('athena:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('athena:connection:applied', listener)

    return () => ipcRenderer.removeListener('athena:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('athena:power-resume', listener)

    return () => ipcRenderer.removeListener('athena:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('athena:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('athena:power-battery', listener)

    return () => ipcRenderer.removeListener('athena:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:boot-progress', listener)

    return () => ipcRenderer.removeListener('athena:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('athena:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('athena:bootstrap:continue-local'),
  resetBootstrap: () => ipcRenderer.invoke('athena:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('athena:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('athena:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('athena:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('athena:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('athena:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('athena:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('athena:uninstall:summary'),
    run: mode => ipcRenderer.invoke('athena:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('athena:updates:check'),
    apply: opts => ipcRenderer.invoke('athena:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('athena:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('athena:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('athena:updates:progress', listener)

      return () => ipcRenderer.removeListener('athena:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('athena:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('athena:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('athena:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('athena:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('athena:found-in-page', listener)

    return () => ipcRenderer.removeListener('athena:found-in-page', listener)
  }
})
