import React, { useState, useRef, useEffect } from 'react';
import { LineChart, Send, User, Bot } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatMessage {
  role: 'user' | 'model';
  text: string;
  timestamp?: string;
  id?: string;
}

export const AdvisorChat: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    // Fetch History
    const fetchHistory = async () => {
      try {
        const idToken = await user?.getIdToken();
        const familyId = user?.uid || 'CURRENT_UID';
        const res = await fetch(`${API_URL}/api/chat/advisor/history?family_id=${familyId}`, {
          headers: idToken ? { 'Authorization': `Bearer ${idToken}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          if (data.history && data.history.length > 0) {
            setMessages(data.history);
          } else {
             // Initial greeting
             setMessages([{
               role: 'model',
               text: 'שלום! אני היועץ הפיננסי שלך (מופעל ע"י AI). פירשתי את היסטוריית תיק המניות שלך ואני מוכן לענות על כל שאלה בנוגע להרכב מניות, פיזור סיכונים או הצעות השקעה לטווח ארוך. \nאיך אוכל לעזור לך היום?',
               id: 'init'
             }]);
          }
        }
      } catch (e) {
        console.error("Failed to fetch history", e);
      } finally {
        setInitialLoading(false);
      }
    };
    if (user) {
       fetchHistory();
    } else {
       setInitialLoading(false);
    }
  }, [user]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const newUserMessage: ChatMessage = {
      role: 'user',
      text: inputValue.trim(),
      id: Date.now().toString(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const idToken = await user?.getIdToken();
      
      const payload = {
        family_id: user?.uid || 'CURRENT_UID',
        question: newUserMessage.text,
      };

      const response = await fetch(`${API_URL}/api/chat/advisor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {})
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to communicate with Advisor API');
      }

      const data = await response.json();
      
      const aiResponse: ChatMessage = {
        role: 'model',
        text: data.response || 'מצטער, משהו השתבש בעיבוד התשובה.',
        id: (Date.now() + 1).toString()
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('Chat error:', error);
      const aiResponse: ChatMessage = {
        role: 'model',
        text: 'מצטער, הייתה לי שגיאת תקשורת עם השרת.',
        id: (Date.now() + 1).toString()
      };
      setMessages((prev) => [...prev, aiResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <div dir="rtl" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full w-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 rounded-t-2xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center text-teal-600 dark:text-teal-400 shadow-inner border border-teal-500/20">
            <LineChart className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-bold text-slate-900 dark:text-slate-100">יועץ השקעות AI</h2>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 font-medium mt-0.5">
               <span className="relative flex h-2 w-2">
                 <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                 <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
               </span>
               מחובר לתיק המסחר שלך
            </div>
          </div>
        </div>
      </div>


      {/* Messages Area */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
        {initialLoading ? (
            <div className="flex items-center justify-center h-full">
               <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-500"></div>
            </div>
        ) : (
            messages.map((msg, idx) => (
            <div
                key={msg.id || idx}
                className={`flex items-start gap-3 flex-row`}
            >
                {/* Avatar */}
                {msg.role === 'user' ? (
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-blue-600 ml-1">
                    <User className="w-4 h-4 text-white" />
                </div>
                ) : (
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 shadow-inner border border-teal-500/20 ml-1 text-teal-600">
                    <Bot className="w-4 h-4" />
                </div>
                )}

                {/* Message Bubble */}
                <div
                className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${
                    msg.role === 'user'
                    ? 'bg-blue-600 rounded-tr-sm text-white shadow-blue-900/20'
                    : 'bg-white dark:bg-slate-800 rounded-tr-sm border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200'
                }`}
                >
                {msg.text}
                </div>
            </div>
            ))
        )}

        {isLoading && (
          <div className="flex items-start gap-3">
             <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 shadow-inner border border-teal-500/20 ml-1 text-teal-600 text-sm font-bold">
              AI
            </div>
            <div className="max-w-[80%] rounded-2xl p-3 text-sm bg-white dark:bg-slate-800 rounded-tr-sm border border-slate-200 dark:border-slate-700/50 text-slate-400 flex items-center gap-2 shadow-sm">
              <span className="flex gap-1 items-center h-4">
                 <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></span>
                 <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.15s'}}></span>
                 <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s'}}></span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-slate-50 dark:bg-slate-800/80 rounded-b-2xl border-t border-slate-100 dark:border-slate-800">
        <div className="relative group/input">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="שאל משו על תיק המניות שלך..."
            className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-full py-3 pr-4 pl-14 text-sm focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/50 transition-all text-slate-900 dark:text-slate-100 placeholder-slate-400 shadow-sm"
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className="absolute left-1.5 top-1.5 w-9 h-9 flex items-center justify-center bg-teal-500 hover:bg-teal-400 hover:scale-105 active:scale-95 disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:text-slate-500 disabled:hover:scale-100 transition-all rounded-full text-white shadow-md shadow-teal-500/20 cursor-pointer"
          >
            <Send className="w-4 h-4 -scale-x-100 transform" />
          </button>
        </div>
      </div>
    </div>
  );
};
