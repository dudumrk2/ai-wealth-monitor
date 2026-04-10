import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, MessageSquarePlus, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}

const CONTEXTS = ['כללי', 'פנסיה', 'בורסה', 'ביטוח'];

const INITIAL_MESSAGE: Message = {
  id: '1',
  role: 'ai',
  content: 'שלום! אני הקופיילוט הפיננסי שלך. איך אוכל לעזור לך היום?',
};

export const CopilotChat: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeContext, setActiveContext] = useState<string>('כללי');
  
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleNewChat = () => {
    setMessages([INITIAL_MESSAGE]);
    setInputValue('');
    setIsLoading(false);
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const newUserMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const idToken = await user?.getIdToken();
      
      const payload = {
        family_id: user?.uid || 'CURRENT_UID',
        question: newUserMessage.content,
        context_filter: activeContext
      };

      const response = await fetch(`${API_URL}/api/chat/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {})
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to communicate with Copilot API');
      }

      const data = await response.json();
      
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: data.response || 'מצטער, משהו השתבש בעיבוד התשובה.',
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('Chat error:', error);
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: 'מצטער, הייתה לי שגיאת תקשורת. נסה שוב מאוחר יותר.',
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
    <div dir="rtl" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full transition-all hover:border-slate-300 dark:hover:border-slate-700 group overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center text-blue-400 shadow-inner border border-blue-500/20">
            <Bot className="w-4 h-4" />
          </div>
          <h2 className="font-semibold text-base text-slate-900 dark:text-slate-100">עוזר AI אישי</h2>
          <span className="mr-auto flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
          </span>
        </div>
        <button
          onClick={handleNewChat}
          className="p-1.5 text-slate-400 hover:text-blue-600 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 rounded-full transition-colors flex items-center justify-center ml-1"
          title="שיחה חדשה"
        >
          <MessageSquarePlus className="w-4 h-4" />
        </button>
      </div>

      {/* Context Chips */}
      <div className="flex bg-slate-50 dark:bg-slate-800/50 px-3 py-2 gap-2 overflow-x-auto border-b border-slate-100 dark:border-slate-800" style={{ scrollbarWidth: 'none' }}>
        {CONTEXTS.map((ctx) => (
          <button
            key={ctx}
            onClick={() => setActiveContext(ctx)}
            className={`whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-medium transition-colors border ${
              activeContext === ctx
                ? 'bg-blue-600 border-blue-600 text-white shadow-sm'
                : 'bg-white dark:bg-slate-700 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-600'
            }`}
          >
            {ctx}
          </button>
        ))}
      </div>

      {/* Messages Area */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row' : 'flex-row'}`}
          >
            {/* Avatar */}
            {msg.role === 'user' ? (
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-blue-600 ml-1">
                <User className="w-5 h-5 text-white" />
              </div>
            ) : (
               <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 shadow-inner border border-blue-500/20 ml-1 text-blue-400">
                <Bot className="w-5 h-5" />
              </div>
            )}

            {/* Message Bubble */}
            <div
              className={`max-w-[85%] rounded-2xl p-3 text-sm leading-relaxed shadow-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 rounded-tr-sm text-white shadow-blue-900/20'
                  : 'bg-white dark:bg-slate-800 rounded-tr-sm border border-slate-200 dark:border-slate-700/50 text-slate-700 dark:text-slate-200'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-start gap-3">
             <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 shadow-inner border border-blue-500/20 ml-1 text-blue-400">
              <Bot className="w-5 h-5" />
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
      <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 rounded-b-2xl">
        <div className="relative group/input">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="שאלו את הקופיילוט..."
            className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700/80 rounded-full py-3 pr-4 pl-14 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all text-slate-900 dark:text-slate-200 placeholder-slate-500 shadow-inner"
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className="absolute left-1.5 top-1.5 w-9 h-9 flex items-center justify-center bg-blue-500 hover:bg-blue-400 hover:scale-105 active:scale-95 disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:text-slate-500 disabled:hover:scale-100 transition-all rounded-full text-white shadow-lg shadow-blue-500/20 cursor-pointer"
          >
            <Send className="w-4 h-4 -scale-x-100 transform" />
          </button>
        </div>
      </div>
    </div>
  );
};
