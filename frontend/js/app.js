/**
 * AI File Organizer - Frontend Application v2.1
 */
(function () {
    "use strict";

    const API = "/api";
    let ws = null;

    // ---- State ----
    let currentPath = "";
    let parentPath = null;
    let scannedFiles = [];
    let classificationResults = [];
    let lastManifestId = "";
    let profiles = [];
    let editingProfileId = null;

    const IMAGE_EXTS = new Set([
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico",
    ]);

    // ---- DOM References ----
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ---- Toast Notification ----
    function toast(message, type = "info", duration = 3500) {
        const container = $("#toastContainer");
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = message;
        el.addEventListener("click", () => {
            el.classList.add("fadeOut");
            setTimeout(() => el.remove(), 300);
        });
        container.appendChild(el);
        setTimeout(() => {
            el.classList.add("fadeOut");
            setTimeout(() => el.remove(), 300);
        }, duration);
    }

    // ---- API Helpers ----
    async function api(url, opts = {}) {
        const resp = await fetch(API + url, {
            headers: { "Content-Type": "application/json", ...opts.headers },
            ...opts,
        });
        const data = await resp.json();
        if (!data.success) throw new Error(data.error || "Unknown error");
        return data.data;
    }

    // ---- Thumbnail Helper ----
    function isImageFile(filename) {
        const ext = "." + filename.split(".").pop().toLowerCase();
        return IMAGE_EXTS.has(ext);
    }

    function thumbCell(filePath, filename) {
        if (isImageFile(filename)) {
            const src = `${API}/thumbnail?path=${encodeURIComponent(filePath)}&size=80`;
            return `<td class="thumb-cell"><img src="${src}" alt="" loading="lazy" onclick="document.getElementById('lightboxImg').src='${API}/thumbnail?path=${encodeURIComponent(filePath)}&size=300';document.getElementById('lightbox').classList.remove('hidden')"></td>`;
        }
        const icon = getFileIcon(filename);
        return `<td class="thumb-cell"><div class="thumb-placeholder">${icon}</div></td>`;
    }

    function getFileIcon(filename) {
        const ext = filename.split(".").pop().toLowerCase();
        const icons = {
            pdf: "\uD83D\uDCC4", doc: "\uD83D\uDCC4", docx: "\uD83D\uDCC4",
            xls: "\uD83D\uDCCA", xlsx: "\uD83D\uDCCA",
            ppt: "\uD83D\uDCCA", pptx: "\uD83D\uDCCA",
            mp4: "\uD83C\uDFA5", avi: "\uD83C\uDFA5", mkv: "\uD83C\uDFA5", mov: "\uD83C\uDFA5",
            mp3: "\uD83C\uDFB5", wav: "\uD83C\uDFB5", flac: "\uD83C\uDFB5", ogg: "\uD83C\uDFB5",
            zip: "\uD83D\uDCE6", rar: "\uD83D\uDCE6", "7z": "\uD83D\uDCE6", tar: "\uD83D\uDCE6",
            py: "\uD83D\uDCBB", js: "\uD83D\uDCBB", ts: "\uD83D\uDCBB", html: "\uD83D\uDCBB",
            exe: "\u2699\uFE0F", msi: "\u2699\uFE0F",
        };
        return icons[ext] || "\uD83D\uDCC1";
    }

    // ---- Lightbox ----
    function initLightbox() {
        $("#lightbox").addEventListener("click", () => {
            $("#lightbox").classList.add("hidden");
        });
    }

    // ---- Navigation ----
    function initNav() {
        $$(".nav-btn").forEach((btn) => {
            btn.addEventListener("click", () => navigateTo(btn.dataset.page));
        });
    }

    function navigateTo(page) {
        $$(".nav-btn").forEach((b) => b.classList.remove("active"));
        $$(`.nav-btn[data-page="${page}"]`).forEach((b) => b.classList.add("active"));
        $$(".page").forEach((p) => p.classList.remove("active"));
        const target = $(`#page-${page}`);
        if (target) target.classList.add("active");

        if (page === "profiles") loadProfiles();
        if (page === "history") loadHistory();
        if (page === "settings") loadConfig();
    }

    // ---- WebSocket ----
    function connectWS() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${proto}//${location.host}/ws/progress`);
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            handleProgress(msg);
        };
        ws.onclose = () => setTimeout(connectWS, 3000);
    }

    function handleProgress(msg) {
        if (msg.stage === "complete") {
            hideProgress();
            toast(msg.message || "완료", "success");
            return;
        }
        if (msg.stage === "error") {
            hideProgress();
            toast(msg.message || "오류 발생", "error");
            return;
        }
        showProgress(msg.message || msg.stage, msg.current, msg.total, msg.current_file);
    }

    function showProgress(title, current, total, file) {
        $("#progressOverlay").classList.remove("hidden");
        $("#progressTitle").textContent = title;
        $("#progressCurrent").textContent = current;
        $("#progressTotal").textContent = total;
        const pct = total > 0 ? Math.round((current / total) * 100) : 0;
        $("#progressBar").style.width = pct + "%";
        $("#progressFile").textContent = file || "";
    }

    function hideProgress() {
        $("#progressOverlay").classList.add("hidden");
    }

    // ---- AI Status (Local Ollama or Remote Server) ----
    let ollamaGuideDismissed = false;

    async function checkOllama() {
        const el = $("#ollamaStatus");
        const guide = $("#ollamaGuide");
        const badge = $("#modeBadge");
        try {
            const data = await api("/ollama/status");
            el.className = "status-indicator connected";

            if (data.mode === "remote") {
                el.querySelector(".label").textContent = "원격 서버 연결됨";
                badge.textContent = "REMOTE";
                badge.className = "mode-badge remote";
            } else {
                el.querySelector(".label").textContent = data.current_model.split(":")[0].split("/").pop();
                badge.textContent = "LOCAL";
                badge.className = "mode-badge";
            }
            if (guide) guide.classList.add("hidden");
        } catch {
            el.className = "status-indicator disconnected";
            el.querySelector(".label").textContent = "AI 연결 실패";
            if (guide && !ollamaGuideDismissed) guide.classList.remove("hidden");
        }
    }

    // ---- Folder Browser ----
    async function browse(path) {
        try {
            const url = path ? `/browse?path=${encodeURIComponent(path)}` : "/browse";
            const data = await api(url);
            currentPath = data.current_path;
            parentPath = data.parent_path;
            $("#inputPath").value = currentPath;
            renderFolders(data.folders);
        } catch (err) {
            toast("폴더 탐색 실패: " + err.message, "error");
        }
    }

    function renderFolders(folders) {
        const list = $("#folderList");
        list.innerHTML = "";
        folders.forEach((f) => {
            const div = document.createElement("div");
            div.className = "folder-item";
            div.textContent = f.name;
            div.addEventListener("click", () => browse(f.path));
            list.appendChild(div);
        });
    }

    function initBrowser() {
        $("#btnBrowseUp").addEventListener("click", () => {
            if (parentPath) browse(parentPath);
            else browse("");
        });

        $("#inputPath").addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const val = $("#inputPath").value.trim();
                if (val) browse(val);
            }
        });

        browse("");
    }

    // ---- Scan ----
    async function scanDirectory() {
        const path = $("#inputPath").value.trim();
        if (!path) { toast("경로를 입력하세요.", "warning"); return; }

        try {
            showProgress("스캔 중...", 0, 0, path);
            const data = await api("/scan", {
                method: "POST",
                body: JSON.stringify({ path, recursive: false }),
            });
            hideProgress();

            scannedFiles = data.files;
            renderScanResult(data);
            await loadProfileSelect();
            toast(`${data.total_files}개 파일 스캔 완료`, "success");
        } catch (err) {
            hideProgress();
            toast("스캔 실패: " + err.message, "error");
        }
    }

    function renderScanResult(data) {
        $("#scanResult").classList.remove("hidden");
        $("#classifyResult").classList.add("hidden");
        $("#executeResult").classList.add("hidden");

        $("#scanTotal").textContent = data.total_files;
        $("#scanSize").textContent = data.total_size_display;

        // Type distribution chips
        const distEl = $("#typeDist");
        distEl.innerHTML = "";
        Object.entries(data.type_distribution).forEach(([ext, count]) => {
            const chip = document.createElement("span");
            chip.className = "type-chip";
            chip.textContent = `${ext} (${count})`;
            distEl.appendChild(chip);
        });

        // File table
        const tbody = $("#fileTableBody");
        tbody.innerHTML = "";
        data.files.forEach((f, i) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><input type="checkbox" class="file-check" data-index="${i}" checked></td>
                ${thumbCell(f.path, f.filename)}
                <td title="${f.path}">${f.filename}</td>
                <td><span class="badge badge-${f.category}">${f.category}</span></td>
                <td>${f.size_display}</td>
                <td>${f.modified.split("T")[0]}</td>
            `;
            tbody.appendChild(tr);
        });

        // Check all + selection info
        $("#checkAll").checked = true;
        updateSelectionInfo();
        $("#checkAll").onchange = (e) => {
            $$(".file-check").forEach((cb) => (cb.checked = e.target.checked));
            updateSelectionInfo();
        };
        // delegate change event on checkboxes
        tbody.addEventListener("change", (e) => {
            if (e.target.classList.contains("file-check")) updateSelectionInfo();
        });
    }

    function updateSelectionInfo() {
        const total = $$(".file-check").length;
        const checked = $$(".file-check:checked").length;
        const el = $("#selectionInfo");
        if (el) el.textContent = `${checked}/${total}개 선택됨`;
    }

    // ---- Profile Select ----
    async function loadProfileSelect() {
        try {
            profiles = await api("/profiles");
            const sel = $("#selectProfile");
            sel.innerHTML = "";
            profiles.forEach((p) => {
                const opt = document.createElement("option");
                opt.value = p.id;
                opt.textContent = p.name;
                sel.appendChild(opt);
            });
            updateProfileDesc();
            sel.addEventListener("change", updateProfileDesc);
        } catch (err) {
            console.error("프로파일 로드 실패:", err);
        }
    }

    function updateProfileDesc() {
        const sel = $("#selectProfile");
        const desc = $("#profileDesc");
        if (!desc) return;
        const p = profiles.find((x) => x.id === sel.value);
        desc.textContent = p ? p.description : "";
        desc.title = p ? p.description : "";
    }

    // ---- Classify ----
    async function classifyFiles() {
        const profileId = $("#selectProfile").value;
        if (!profileId) { toast("프로파일을 선택하세요.", "warning"); return; }

        // 선택된 파일만
        const checked = $$(".file-check:checked");
        const selectedFiles = Array.from(checked).map((cb) => scannedFiles[cb.dataset.index]);
        if (selectedFiles.length === 0) { toast("파일을 선택하세요.", "warning"); return; }

        const basePath = $("#inputPath").value.trim();

        try {
            showProgress("분류 중...", 0, selectedFiles.length, "");
            const data = await api("/classify", {
                method: "POST",
                body: JSON.stringify({
                    base_path: basePath,
                    files: selectedFiles,
                    profile_id: profileId,
                }),
            });
            hideProgress();

            classificationResults = data.results;
            renderClassifyResult(data);
            toast(`${data.classified}개 파일 분류 완료`, "success");
        } catch (err) {
            hideProgress();
            toast("분류 실패: " + err.message, "error");
        }
    }

    function renderClassifyResult(data) {
        $("#classifyResult").classList.remove("hidden");
        $("#executeResult").classList.add("hidden");

        $("#classifiedCount").textContent = data.classified;
        $("#classifyErrors").textContent = data.errors;

        // Folder summary chips
        const summaryEl = $("#folderSummary");
        summaryEl.innerHTML = "";
        Object.entries(data.folder_summary).forEach(([folder, count]) => {
            const chip = document.createElement("span");
            chip.className = "folder-chip";
            chip.innerHTML = `<strong>${folder}</strong> ${count}`;
            summaryEl.appendChild(chip);
        });

        // Results table
        const tbody = $("#classifyTableBody");
        tbody.innerHTML = "";
        data.results.forEach((r) => {
            const tr = document.createElement("tr");
            const statusBadge = r.status === "success"
                ? '<span class="badge badge-success">OK</span>'
                : '<span class="badge badge-error">Error</span>';
            tr.innerHTML = `
                ${thumbCell(r.file_path, r.filename)}
                <td title="${r.file_path}">${r.filename}</td>
                <td><strong>${r.target_folder}</strong></td>
                <td>${r.new_name || "-"}</td>
                <td title="${r.description}">${(r.description || "").slice(0, 40)}</td>
                <td>${statusBadge}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ---- Execute ----
    async function executePlan() {
        const basePath = $("#inputPath").value.trim();
        const mode = $("#selectMode").value;

        try {
            showProgress("실행 중...", 0, classificationResults.length, "");
            const data = await api("/execute", {
                method: "POST",
                body: JSON.stringify({
                    base_path: basePath,
                    results: classificationResults,
                    operation_mode: mode,
                }),
            });
            hideProgress();

            lastManifestId = data.manifest_id;
            renderExecuteResult(data);
            toast(`${data.success}개 파일 ${mode === "move" ? "이동" : "복사"} 완료`, "success");
        } catch (err) {
            hideProgress();
            toast("실행 실패: " + err.message, "error");
        }
    }

    function renderExecuteResult(data) {
        $("#executeResult").classList.remove("hidden");
        $("#classifyResult").classList.add("hidden");
        $("#scanResult").classList.add("hidden");

        const summary = $("#resultSummary");
        summary.innerHTML = `
            <div class="stat success">성공: ${data.success}</div>
            <div class="stat failed">실패: ${data.failed}</div>
            <div class="stat skipped">건너뜀: ${data.skipped}</div>
        `;
    }

    // ---- Undo ----
    async function undoLast() {
        if (!lastManifestId) { toast("되돌릴 작업이 없습니다.", "warning"); return; }
        try {
            const data = await api("/undo", {
                method: "POST",
                body: JSON.stringify({ manifest_id: lastManifestId }),
            });
            toast(`되돌리기 완료: ${data.success}/${data.total}`, "success");
            lastManifestId = "";
        } catch (err) {
            toast("되돌리기 실패: " + err.message, "error");
        }
    }

    function newScan() {
        $("#scanResult").classList.add("hidden");
        $("#classifyResult").classList.add("hidden");
        $("#executeResult").classList.add("hidden");
        scannedFiles = [];
        classificationResults = [];
    }

    // ---- Profiles Page ----
    async function loadProfiles() {
        try {
            profiles = await api("/profiles");
            renderProfileGrid();
        } catch (err) {
            console.error("프로파일 로드 실패:", err);
        }
    }

    function renderProfileGrid() {
        const grid = $("#profileGrid");
        grid.innerHTML = "";
        profiles.forEach((p) => {
            const card = document.createElement("div");
            card.className = "profile-card";
            const folders = p.folders.map((f) => `<span class="mini-tag">${f.name}</span>`).join("");
            card.innerHTML = `
                <div class="profile-card-header">
                    <h3>${p.name}</h3>
                    ${p.is_default ? '<span class="tag">기본</span>' : ""}
                </div>
                <p class="profile-desc">${p.description || ""}</p>
                <div class="profile-folders">${folders}</div>
                <div class="profile-actions">
                    <button class="btn btn-sm btn-edit" data-id="${p.id}">편집</button>
                    <button class="btn btn-sm btn-dup" data-id="${p.id}">복제</button>
                    ${!p.is_default ? `<button class="btn btn-sm btn-danger btn-del" data-id="${p.id}">삭제</button>` : ""}
                </div>
            `;
            grid.appendChild(card);
        });

        // Event delegation
        grid.querySelectorAll(".btn-edit").forEach((b) =>
            b.addEventListener("click", () => openProfileModal(b.dataset.id))
        );
        grid.querySelectorAll(".btn-dup").forEach((b) =>
            b.addEventListener("click", () => duplicateProfile(b.dataset.id))
        );
        grid.querySelectorAll(".btn-del").forEach((b) =>
            b.addEventListener("click", () => deleteProfile(b.dataset.id))
        );
    }

    // ---- Profile Modal ----
    function openProfileModal(profileId) {
        editingProfileId = profileId || null;
        const modal = $("#profileModal");

        if (profileId) {
            const p = profiles.find((x) => x.id === profileId);
            if (!p) return;
            $("#modalTitle").textContent = "프로파일 편집";
            $("#profName").value = p.name;
            $("#profDesc").value = p.description || "";
            $("#profPrompt").value = p.prompt;
            $("#profRenamePattern").value = p.rename_pattern || "{description}";
            $("#profEnableRename").checked = p.enable_rename;
            renderFolderInputs(p.folders);
        } else {
            $("#modalTitle").textContent = "새 프로파일";
            $("#profName").value = "";
            $("#profDesc").value = "";
            $("#profPrompt").value = "";
            $("#profRenamePattern").value = "{description}";
            $("#profEnableRename").checked = true;
            renderFolderInputs([
                { name: "", description: "" },
                { name: "", description: "" },
            ]);
        }

        modal.classList.remove("hidden");
    }

    function renderFolderInputs(folders) {
        const container = $("#folderInputs");
        container.innerHTML = "";
        folders.forEach((f, i) => {
            const row = document.createElement("div");
            row.className = "folder-input-row";
            row.innerHTML = `
                <input type="text" placeholder="폴더 이름" value="${f.name || ""}" class="fi-name">
                <input type="text" placeholder="설명" value="${f.description || ""}" class="fi-desc">
                <button class="btn-remove" title="삭제">&times;</button>
            `;
            row.querySelector(".btn-remove").addEventListener("click", () => row.remove());
            container.appendChild(row);
        });
    }

    function closeProfileModal() {
        $("#profileModal").classList.add("hidden");
        editingProfileId = null;
    }

    async function saveProfile() {
        const name = $("#profName").value.trim();
        const prompt = $("#profPrompt").value.trim();
        if (!name) { toast("이름을 입력하세요.", "warning"); return; }
        if (!prompt) { toast("프롬프트를 입력하세요.", "warning"); return; }

        const folderRows = $$("#folderInputs .folder-input-row");
        const folders = [];
        folderRows.forEach((row) => {
            const n = row.querySelector(".fi-name").value.trim();
            const d = row.querySelector(".fi-desc").value.trim();
            if (n) folders.push({ name: n, description: d });
        });
        if (folders.length < 2) { toast("폴더는 최소 2개 이상 필요합니다.", "warning"); return; }

        const payload = {
            name,
            description: $("#profDesc").value.trim(),
            prompt,
            folders,
            rename_pattern: $("#profRenamePattern").value.trim() || "{description}",
            enable_rename: $("#profEnableRename").checked,
        };

        try {
            if (editingProfileId) {
                await api(`/profiles/${editingProfileId}`, {
                    method: "PUT",
                    body: JSON.stringify(payload),
                });
            } else {
                await api("/profiles", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            }
            closeProfileModal();
            loadProfiles();
            toast("프로파일 저장 완료", "success");
        } catch (err) {
            toast("저장 실패: " + err.message, "error");
        }
    }

    async function duplicateProfile(id) {
        try {
            await api(`/profiles/${id}/duplicate`, { method: "POST" });
            loadProfiles();
            toast("프로파일이 복제되었습니다.", "success");
        } catch (err) {
            toast("복제 실패: " + err.message, "error");
        }
    }

    async function deleteProfile(id) {
        if (!confirm("이 프로파일을 삭제하시겠습니까?")) return;
        try {
            await api(`/profiles/${id}`, { method: "DELETE" });
            loadProfiles();
            toast("프로파일이 삭제되었습니다.", "info");
        } catch (err) {
            toast("삭제 실패: " + err.message, "error");
        }
    }

    // ---- History Page ----
    async function loadHistory() {
        try {
            const data = await api("/manifests");
            renderHistory(data);
        } catch (err) {
            console.error("이력 로드 실패:", err);
        }
    }

    function renderHistory(manifests) {
        const list = $("#historyList");
        list.innerHTML = "";
        if (manifests.length === 0) {
            list.innerHTML = '<p style="color:var(--text-dim)">아직 작업 이력이 없습니다.</p>';
            return;
        }
        manifests.forEach((m) => {
            const item = document.createElement("div");
            item.className = "history-item";
            item.innerHTML = `
                <div class="info">
                    <strong>${m.manifest_id}</strong>
                    <div class="meta">${m.base_path} | ${m.operation_mode} | ${m.total_files}개 파일</div>
                    <div class="meta">${m.timestamp}</div>
                </div>
                <button class="btn btn-sm btn-undo" data-id="${m.manifest_id}">되돌리기</button>
            `;
            item.querySelector(".btn-undo").addEventListener("click", async () => {
                if (!confirm(`작업 ${m.manifest_id}을 되돌리시겠습니까?`)) return;
                try {
                    const data = await api("/undo", {
                        method: "POST",
                        body: JSON.stringify({ manifest_id: m.manifest_id }),
                    });
                    toast(`되돌리기 완료: ${data.success}/${data.total}`, "success");
                    loadHistory();
                } catch (err) {
                    toast("되돌리기 실패: " + err.message, "error");
                }
            });
            list.appendChild(item);
        });
    }

    // ---- Settings Page ----
    function toggleModeSettings() {
        const mode = $("#cfgMode").value;
        const local = $("#localSettings");
        const remote = $("#remoteSettings");
        const serverKey = $("#serverKeySection");
        if (mode === "remote") {
            local.classList.add("hidden");
            remote.classList.remove("hidden");
            serverKey.classList.add("hidden");
        } else {
            local.classList.remove("hidden");
            remote.classList.add("hidden");
            serverKey.classList.remove("hidden");
        }
    }

    async function loadConfig() {
        try {
            const data = await api("/config");
            $("#cfgOllamaUrl").value = data.ollama.url;
            $("#cfgModel").value = data.ollama.model;
            $("#cfgTimeout").value = data.ollama.timeout;
            $("#cfgOperationMode").value = data.processing.operation_mode;
            $("#cfgRecursive").checked = data.processing.scan_recursive;
            $("#cfgSkipHidden").checked = data.processing.skip_hidden;
            $("#cfgSkipSystem").checked = data.processing.skip_system;
            $("#cfgLanguage").value = data.language;

            // 모드 설정
            $("#cfgMode").value = data.mode || "local";
            $("#cfgRemoteUrl").value = (data.remote && data.remote.url) || "";
            $("#cfgRemoteApiKey").value = (data.remote && data.remote.api_key) || "";
            $("#cfgServerApiKey").value = data.api_key || "";
            toggleModeSettings();
        } catch (err) {
            console.error("설정 로드 실패:", err);
        }
    }

    async function saveConfig() {
        const mode = $("#cfgMode").value;
        const payload = {
            ollama: {
                url: $("#cfgOllamaUrl").value.trim(),
                model: $("#cfgModel").value.trim(),
                timeout: parseInt($("#cfgTimeout").value) || 120,
            },
            processing: {
                operation_mode: $("#cfgOperationMode").value,
                scan_recursive: $("#cfgRecursive").checked,
                skip_hidden: $("#cfgSkipHidden").checked,
                skip_system: $("#cfgSkipSystem").checked,
            },
            language: $("#cfgLanguage").value,
            mode: mode,
            remote: {
                url: $("#cfgRemoteUrl").value.trim(),
                api_key: $("#cfgRemoteApiKey").value.trim(),
            },
        };
        try {
            await api("/config", { method: "PUT", body: JSON.stringify(payload) });
            toast("설정이 저장되었습니다.", "success");
            checkOllama();
        } catch (err) {
            toast("설정 저장 실패: " + err.message, "error");
        }
    }

    async function generateApiKey() {
        try {
            const data = await api("/generate-api-key", { method: "POST" });
            $("#cfgServerApiKey").value = data.api_key;
            toast("새 API 키가 생성되었습니다. 이 키를 원격 사용자에게 전달하세요.", "success", 5000);
        } catch (err) {
            toast("API 키 생성 실패: " + err.message, "error");
        }
    }

    // ---- Init ----
    function init() {
        initNav();
        initBrowser();
        initLightbox();
        connectWS();
        checkOllama();

        // Home page buttons
        $("#btnScan").addEventListener("click", scanDirectory);
        $("#btnClassify").addEventListener("click", classifyFiles);
        $("#btnExecute").addEventListener("click", executePlan);
        $("#btnUndoLast").addEventListener("click", undoLast);
        $("#btnNewScan").addEventListener("click", newScan);

        // Profile page buttons
        $("#btnNewProfile").addEventListener("click", () => openProfileModal(null));
        $("#btnCloseModal").addEventListener("click", closeProfileModal);
        $("#btnCancelProfile").addEventListener("click", closeProfileModal);
        $("#btnSaveProfile").addEventListener("click", saveProfile);
        $("#btnAddFolder").addEventListener("click", () => {
            renderFolderInputs([
                ...Array.from($$("#folderInputs .folder-input-row")).map((row) => ({
                    name: row.querySelector(".fi-name").value,
                    description: row.querySelector(".fi-desc").value,
                })),
                { name: "", description: "" },
            ]);
        });

        // Settings
        $("#btnSaveConfig").addEventListener("click", saveConfig);
        $("#cfgMode").addEventListener("change", toggleModeSettings);
        $("#btnGenerateApiKey").addEventListener("click", generateApiKey);

        // Ollama guide
        const dismissBtn = $("#btnDismissGuide");
        if (dismissBtn) {
            dismissBtn.addEventListener("click", () => {
                ollamaGuideDismissed = true;
                $("#ollamaGuide").classList.add("hidden");
            });
        }
        const retryBtn = $("#btnRetryOllama");
        if (retryBtn) {
            retryBtn.addEventListener("click", () => {
                checkOllama();
                toast("Ollama 연결 확인 중...", "info", 2000);
            });
        }

        // Periodic ollama check
        setInterval(checkOllama, 30000);
    }

    document.addEventListener("DOMContentLoaded", init);
})();
