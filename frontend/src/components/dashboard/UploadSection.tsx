import { useState, useRef, useCallback } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import type { User } from 'firebase/auth';
import { Upload, X, FileText, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const MAX_FILES = 2;

interface Props {
  user: User;
  onSuccess: () => void;
}

type UploadState = 'idle' | 'uploading' | 'success' | 'error';

export default function UploadSection({ user, onSuccess }: Props) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver]       = useState(false);
  const [uploadState, setUploadState]     = useState<UploadState>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── File management ───────────────────────────────────────────────────────

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const pdfs = Array.from(incoming).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfs.length !== incoming.length) {
      setUploadState('error');
      setStatusMessage('ניתן להעלות קבצי PDF בלבד.');
      return;
    }
    setSelectedFiles(prev => {
      const merged = [...prev, ...pdfs];
      if (merged.length > MAX_FILES) {
        setUploadState('error');
        setStatusMessage(`ניתן לבחור לכל היותר ${MAX_FILES} קבצים.`);
        return prev;
      }
      setUploadState('idle');
      setStatusMessage('');
      return merged;
    });
  }, []);

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setUploadState('idle');
    setStatusMessage('');
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
    // Reset input so the same file can be re-selected after removal
    e.target.value = '';
  };

  // ── Drag & Drop ───────────────────────────────────────────────────────────

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
  };

  // ── Upload ────────────────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || uploadState === 'uploading') return;

    setUploadState('uploading');
    setStatusMessage('מעבד דוחות… זה עשוי לקחת כדקה.');

    try {
      const idToken = await user.getIdToken();

      const formData = new FormData();
      selectedFiles.forEach(file => formData.append('files', file));
      formData.append('uid', user.uid);

      const res = await fetch(`${API_URL}/api/process-reports`, {
        method: 'POST',
        headers: {
          // Do NOT set Content-Type manually — the browser sets it (with boundary)
          Authorization: `Bearer ${idToken}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || `שגיאת שרת (${res.status})`);
      }

      const data = await res.json();
      const count = data.processed_count ?? selectedFiles.length;
      setUploadState('success');
      setStatusMessage(`✅ עובדו ${count} קובץ/קבצים בהצלחה! הדאשבורד יתרענן.`);
      setSelectedFiles([]);
      onSuccess();
    } catch (err: any) {
      console.error('[UploadSection] Upload error:', err);
      setUploadState('error');
      setStatusMessage(err.message || 'אירעה שגיאה בעיבוד הדוחות.');
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const canUpload = selectedFiles.length > 0 && uploadState !== 'uploading';

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm mb-6 transition-colors font-sans">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
          <Upload className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <h2 className="font-bold text-slate-800 dark:text-slate-100 text-sm leading-tight">העלאת דוחות פנסיה</h2>
          <p className="text-slate-400 dark:text-slate-500 text-xs">עד {MAX_FILES} קבצי PDF — מעובדים ישירות בענן</p>
        </div>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={clsx(
          'relative border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center gap-2',
          'cursor-pointer transition-all duration-200 select-none',
          isDragOver
            ? 'border-blue-400 bg-blue-50/70 dark:bg-blue-900/20 scale-[1.01]'
            : 'border-slate-200 dark:border-slate-800 hover:border-blue-300 dark:hover:border-blue-800 hover:bg-slate-50/60 dark:hover:bg-slate-800/30',
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileInputChange}
          className="hidden"
        />
        <div className={clsx(
          'p-3 rounded-full transition-colors',
          isDragOver ? 'bg-blue-100 dark:bg-blue-900/50' : 'bg-slate-100 dark:bg-slate-800',
        )}>
          <Upload className={clsx('w-5 h-5', isDragOver ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-slate-500')} />
        </div>
        <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
          {isDragOver ? 'שחרר כאן…' : 'גרור ושחרר קבצי PDF, או לחץ לבחירה'}
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500">PDF בלבד · עד {MAX_FILES} קבצים</p>
      </div>

      {/* Selected files list */}
      {selectedFiles.length > 0 && (
        <div className="mt-3 space-y-2">
          {selectedFiles.map((file, i) => (
            <div
              key={`${file.name}-${i}`}
              className="flex items-center justify-between px-3 py-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800"
            >
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="w-4 h-4 text-blue-500 dark:text-blue-400 flex-shrink-0" />
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate" title={file.name}>
                  {file.name}
                </span>
                <span className="text-xs text-slate-400 dark:text-slate-500 flex-shrink-0">
                  ({(file.size / 1024).toFixed(0)} KB)
                </span>
              </div>
              <button
                onClick={e => { e.stopPropagation(); removeFile(i); }}
                className="p-1 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/50 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors flex-shrink-0"
                aria-label={`הסר ${file.name}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Status message */}
      {statusMessage && (
        <div className={clsx(
          'mt-3 flex items-start gap-2 text-xs rounded-lg px-3 py-2',
          uploadState === 'error'   && 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-100 dark:border-red-900/30',
          uploadState === 'success' && 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-100 dark:border-green-900/30',
          uploadState === 'uploading' && 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border border-blue-100 dark:border-blue-800',
        )}>
          {uploadState === 'uploading' && <Loader2 className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 animate-spin" />}
          {uploadState === 'success'   && <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
          {uploadState === 'error'     && <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />}
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Action button */}
      <div className="mt-4 flex justify-end">
        <button
          onClick={handleUpload}
          disabled={!canUpload}
          className={clsx(
            'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200',
            canUpload
              ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow-md active:scale-95'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed',
          )}
        >
          {uploadState === 'uploading'
            ? <><Loader2 className="w-4 h-4 animate-spin" /> מעבד…</>
            : <><Upload className="w-4 h-4" /> עבד דוחות</>
          }
        </button>
      </div>
    </div>
  );
}
