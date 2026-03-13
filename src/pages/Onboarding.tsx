 import React from 'react'; 
import { useNavigate } from 'react-router-dom';
import { Users, Plus, CheckCircle2, ChevronRight, AlertCircle } from 'lucide-react';

export default function Onboarding() {
  const navigate = useNavigate();
  const [emails, setEmails] = useState(['']);
  
  const handleAddEmail = () => setEmails([...emails, '']);
  const handleEmailChange = (index: number, value: string) => {
    const newEmails = [...emails];
    newEmails[index] = value;
    setEmails(newEmails);
  };

  const handleCompleteSetup = () => {
    // In a real app we would save these to Firestore here
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center py-12 px-4 selection:bg-blue-100">
      
      <div className="w-full max-w-2xl bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden">
        
        {/* Header Area */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 p-8 text-white relative overflow-hidden">
          <div className="absolute right-0 top-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3"></div>
          <div className="relative z-10 flex items-center gap-4 mb-4">
            <div className="bg-white/20 p-3 rounded-2xl backdrop-blur-sm">
              <Users className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Family Setup</h1>
              <p className="text-blue-100 mt-1">Configure who has access to your household data.</p>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="p-8">
          
          <div className="flex items-start gap-4 p-4 mb-8 bg-blue-50 text-blue-800 rounded-2xl border border-blue-100">
             <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" />
             <div className="text-sm">
                <p className="font-semibold mb-1">Security First</p>
                <p>Because financial data is sensitive, ONLY Google accounts listed below will be able to access the joint dashboard. You can modify this later in Settings.</p>
             </div>
          </div>

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Household Name</label>
              <input 
                type="text" 
                placeholder="e.g. The Cohen Family"
                defaultValue="The Cohen Family"
                className="w-full border border-slate-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow"
              />
            </div>

            <div>
               <div className="flex items-center justify-between mb-2">
                 <label className="block text-sm font-semibold text-slate-700">Authorized Google Accounts</label>
               </div>
               
               <div className="space-y-3">
                  {emails.map((email, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="flex-1 relative">
                        <input 
                          type="email" 
                          placeholder="spouse@gmail.com"
                          value={email}
                          onChange={(e) => handleEmailChange(i, e.target.value)}
                          className="w-full border border-slate-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow"
                        />
                        {i === 0 && <CheckCircle2 className="absolute right-3 top-3.5 w-5 h-5 text-emerald-500" />}
                      </div>
                    </div>
                  ))}
               </div>
               
               <button 
                 onClick={handleAddEmail}
                 className="mt-4 flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
               >
                 <Plus className="w-4 h-4" /> Add another account
               </button>
            </div>
          </div>

          <hr className="my-8 border-slate-200" />

          <div className="flex justify-end gap-4">
             <button 
                onClick={handleCompleteSetup}
                className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-8 py-3.5 rounded-xl font-semibold transition-all transform active:scale-95 shadow-lg shadow-slate-900/20"
             >
                Complete Setup <ChevronRight className="w-4 h-4" />
             </button>
          </div>

        </div>
      </div>

    </div>
  );
}
