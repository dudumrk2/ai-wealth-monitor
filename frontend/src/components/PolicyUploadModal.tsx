import React, { useState } from 'react';
import { X, Upload, FileText, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PolicyUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  policyId: string;
  policyName: string;
  uid: string;
}

const PolicyUploadModal: React.FC<PolicyUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  policyId,
  policyName,
  uid
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { user } = useAuth();

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type !== 'application/pdf') {
        setError('אנא בחר קובץ PDF בלבד');
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uid', uid);
    formData.append('document_type', 'specific_policy');
    formData.append('policy_id', policyId);

    try {
      const token = user ? await user.getIdToken() : localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'העלאה נכשלה');
      }

      setSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
        // Reset state for future use
        setFile(null);
        setSuccess(false);
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'אירעה שגיאה בעת העלאת הקובץ');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-blue-500/10 p-2 text-blue-400 rounded-lg">
              <Upload size={20} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">העלאת פוליסה</h3>
              <p className="text-xs text-slate-400">{policyName}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-8">
          {success ? (
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="w-16 h-16 bg-green-500/20 text-green-500 rounded-full flex items-center justify-center mb-4">
                <CheckCircle2 size={32} />
              </div>
              <h4 className="text-xl font-bold text-white mb-2">ההעלאה הושלמה!</h4>
              <p className="text-slate-400 text-sm">הפוליסה נשלחה לניתוח AI ומעודכנת כעת בתיק שלך.</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div 
                className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-all ${
                  file ? 'border-blue-500/50 bg-blue-500/5' : 'border-slate-700 hover:border-slate-600 bg-slate-800/50'
                }`}
              >
                <input 
                  type="file" 
                  id="policy-file" 
                  className="hidden" 
                  accept=".pdf"
                  onChange={handleFileChange}
                />
                <label 
                  htmlFor="policy-file"
                  className="cursor-pointer flex flex-col items-center"
                >
                  {file ? (
                    <>
                      <FileText size={48} className="text-blue-400 mb-3" />
                      <span className="text-white font-medium text-sm text-center line-clamp-1 px-4">{file.name}</span>
                      <span className="text-slate-500 text-xs mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                    </>
                  ) : (
                    <>
                      <div className="w-12 h-12 bg-slate-700 text-slate-400 rounded-full flex items-center justify-center mb-3">
                        <Upload size={24} />
                      </div>
                      <span className="text-slate-300 font-medium">לחץ לבחירת קובץ PDF</span>
                      <span className="text-slate-500 text-xs mt-1">או גרור ושחרר כאן</span>
                    </>
                  )}
                </label>
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-center gap-3 text-red-500 text-sm">
                  <AlertCircle size={18} />
                  <span>{error}</span>
                </div>
              )}

              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className={`w-full py-3.5 rounded-xl font-bold transition-all flex items-center justify-center gap-2 ${
                  !file || uploading 
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed' 
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 active:scale-[0.98]'
                }`}
              >
                {uploading ? (
                  <>
                    <Loader2 size={20} className="animate-spin" />
                    מעבד מסמך...
                  </>
                ) : (
                  <>
                    <Upload size={20} />
                    העלה ונתח פוליסה
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PolicyUploadModal;
