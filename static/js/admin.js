/**
 * Nexus Analytics — Admin panel controller
 * Drag-and-drop upload zone, file validation, retrain feedback.
 */

(function () {
    'use strict';

    /* ============================================================
       Dropzone
       ============================================================ */
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const dzIdle = document.getElementById('dzIdle');
    const dzFile = document.getElementById('dzFile');
    const dzName = document.getElementById('dzFileName');
    const dzSize = document.getElementById('dzFileSize');
    const dzClear = document.getElementById('dzClear');
    const uploadForm = document.getElementById('uploadForm');

    const ALLOWED = ['.csv', '.xlsx', '.xls'];
    const MAX_BYTES = 16 * 1024 * 1024;

    function humanSize(bytes) {
        if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + ' MB';
        return (bytes / 1024).toFixed(1) + ' KB';
    }

    function showFile(file) {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!ALLOWED.includes(ext)) {
            toast(`Unsupported file type "${ext}". Use CSV/XLSX/XLS.`, 'danger');
            return;
        }
        if (file.size > MAX_BYTES) {
            toast(`File too large (${humanSize(file.size)}). Max 16 MB.`, 'danger');
            return;
        }

        dzName.textContent = file.name;
        dzSize.textContent = humanSize(file.size);
        dzIdle.hidden = true;
        dzFile.hidden = false;
        window.refreshIcons();
    }

    function clearFile() {
        if (fileInput) fileInput.value = '';
        dzIdle.hidden = false;
        dzFile.hidden = true;
    }

    dropzone?.addEventListener('click', (e) => {
        if (e.target.closest('#dzClear')) return;
        fileInput?.click();
    });

    fileInput?.addEventListener('change', () => {
        if (fileInput.files[0]) showFile(fileInput.files[0]);
    });

    dzClear?.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });

    ['dragenter', 'dragover'].forEach((evt) =>
        dropzone?.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.add('drag');
        })
    );

    ['dragleave', 'drop'].forEach((evt) =>
        dropzone?.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag');
        })
    );

    dropzone?.addEventListener('drop', (e) => {
        const file = e.dataTransfer?.files?.[0];
        if (!file) return;
        // Assign to the form input via DataTransfer so submit includes it
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        showFile(file);
    });

    uploadForm?.addEventListener('submit', (e) => {
        if (!fileInput?.files?.length) {
            e.preventDefault();
            toast('Choose a file first.', 'warning');
            return;
        }
        const btn = document.getElementById('btnUpload');
        btn.classList.add('loading');
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Cleaning…';
    });

    /* ============================================================
       Retrain button feedback
       ============================================================ */
    const retrainForm = document.getElementById('retrainForm');
    retrainForm?.addEventListener('submit', () => {
        const btn = document.getElementById('btnRetrain');
        btn.classList.add('loading');
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Training…';
    });

    /* ============================================================
       Scroll to #models if hash present
       ============================================================ */
    if (location.hash === '#models') {
        setTimeout(() => {
            document.getElementById('models')?.scrollIntoView({ behavior: 'smooth' });
        }, 250);
    }
})();
