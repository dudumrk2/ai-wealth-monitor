import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, MessageSquarePlus, User, Copy, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../lib/api';
import { getTranslation } from '../utils/i18n';

export interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}

export const CopilotChat: React.FC = () => {
  const { user, isDemo, isEnglishDemo } = useAuth();
  const t = getTranslation(isEnglishDemo);

  const initialMessage: Message = {
    id: '1',
    role: 'ai',
    content: t.copilot.initialMessage,
  };

  const contexts = isEnglishDemo 
    ? ['General', 'Retirement', 'Equities', 'Insurance & RAG']
    : ['כללי', 'פנסיה', 'בורסה', 'ביטוח'];

  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeContext, setActiveContext] = useState<string>(contexts[0]);
  const [isCopied, setIsCopied] = useState(false);
  
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
    setMessages([initialMessage]);
    setInputValue('');
    setIsLoading(false);
  };

  const sendQuery = async (queryText: string) => {
    if (!queryText.trim()) return;

    const newUserMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: queryText.trim(),
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
        content: data.response || (isDemo ? 'Processing error. Please try again.' : 'מצטער, משהו השתבש בעיבוד התשובה.'),
      };
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('Chat error:', error);
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: isDemo ? 'Communication error with AI service.' : 'מצטער, הייתה לי שגיאת תקשורת. נסה שוב מאוחר יותר.',
      };
      setMessages((prev) => [...prev, aiResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = () => {
    sendQuery(inputValue);
  };

  const handleCopyPrompt = async () => {
    try {
      const idToken = await user?.getIdToken();
      const res = await fetch(`${API_URL}/api/chat/copilot/prompt?context_filter=${encodeURIComponent(activeContext)}`, {
        headers: idToken ? { 'Authorization': `Bearer ${idToken}` } : {}
      });
      
      if (res.ok) {
        const data = await res.json();
        await navigator.clipboard.writeText(data.prompt);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      }
    } catch (err) {
      console.error("Failed to copy prompt", err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  const quickPrompts = isEnglishDemo ? [
    { label: '🩺 Policy RAG: Experimental Abroad', query: 'Does my health insurance policy cover experimental treatments abroad?' },
    { label: '📈 Stock Portfolio Summary', query: 'Summarize our active stock holdings and return.' },
    { label: '💰 Retirement Projections', query: 'What is our total retirement portfolio balance and return?' },
  ] : [
    { label: '🩺 כיסוי טיפולים בחו"ל', query: 'האם ביטוח הבריאות שלי מכסה טיפולים ניסיוניים בחו"ל?' },
    { label: '📈 סיכום תיק מניות', query: 'תן לי סיכום של תיק המניות והרווח הכולל' },
    { label: '💰 פנסיה וחיסכון', query: 'מה מצב החיסכון הפנסיוני של המשפחה?' },
  ];

  return (
    <div dir={isEnglishDemo ? "ltr" : "rtl"} className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full transition-all hover:border-slate-300 dark:hover:border-slate-700 group overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center text-blue-400 shadow-inner border border-blue-500/20">
            <Bot className="w-4 h-4" />
          </div>
          <h2 className="font-semibold text-base text-slate-900 dark:text-slate-100">{t.copilot.title}</h2>
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopyPrompt}
            className={`p-1.5 rounded-lg transition-all flex items-center gap-2 text-xs font-bold ${
              isCopied 
                ? 'bg-emerald-500 text-white' 
                : 'text-slate-400 hover:text-emerald-500 hover:bg-white dark:hover:bg-slate-700'
            }`}
            title="Copy Prompt"
          >
            {isCopied ? (isEnglishDemo ? 'Copied!' : 'הועתק!') : (isEnglishDemo ? 'Copy Prompt' : 'העתק פרומפט')}
            <Copy className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleNewChat}
            className="p-1.5 text-slate-400 hover:text-blue-600 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 rounded-full transition-colors flex items-center justify-center"
            title={t.copilot.newChat}
          >
            <MessageSquarePlus className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Context Chips */}
      <div className="flex bg-slate-50 dark:bg-slate-800/50 px-3 py-2 gap-2 overflow-x-auto border-b border-slate-100 dark:border-slate-800" style={{ scrollbarWidth: 'none' }}>
        {contexts.map((ctx) => (
          <button
            key={ctx}
            onClick={() => setActiveContext(ctx)}
            className={`whitespace-nowrap px-3.5 py-1 rounded-full text-xs font-semibold transition-colors border ${
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
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className="flex items-start gap-2.5"
          >
            {/* Avatar */}
            {msg.role === 'user' ? (
              <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-blue-600 text-white">
                <User className="w-4 h-4" />
              </div>
            ) : (
               <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 shadow-inner border border-blue-500/20 text-blue-400">
                <Bot className="w-4 h-4" />
              </div>
            )}

            {/* Message Bubble */}
            <div
              className={`max-w-[85%] rounded-2xl p-3 text-xs md:text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white shadow-blue-900/20'
                  : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/50 text-slate-800 dark:text-slate-200'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-start gap-2.5">
             <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 shadow-inner border border-blue-500/20 text-blue-400">
              <Bot className="w-4 h-4" />
            </div>
            <div className="max-w-[80%] rounded-2xl p-3 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/50 text-slate-400 flex items-center gap-2 shadow-sm">
              <span className="flex gap-1 items-center h-4">
                 <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></span>
                 <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.15s'}}></span>
                 <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.3s'}}></span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Quick Prompts */}
      <div className="px-3 py-1.5 bg-slate-50/80 dark:bg-slate-800/40 border-t border-slate-100 dark:border-slate-800 flex gap-1.5 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
        {quickPrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => sendQuery(p.query)}
            className="whitespace-nowrap px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-blue-500 hover:text-blue-600 dark:hover:text-blue-400 transition-all shrink-0 flex items-center gap-1 shadow-2xs"
          >
            <Sparkles className="w-3 h-3 text-amber-500" />
            {p.label}
          </button>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 rounded-b-2xl">
        <div className="relative group/input flex items-center">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t.copilot.placeholder}
            className={`w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700/80 rounded-full py-2.5 text-xs md:text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 transition-all text-slate-900 dark:text-slate-200 placeholder-slate-400 shadow-inner ${
              isDemo ? 'pl-4 pr-12' : 'pr-4 pl-12'
            }`}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className={`absolute top-1.5 w-8 h-8 flex items-center justify-center bg-blue-600 hover:bg-blue-500 hover:scale-105 active:scale-95 disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:text-slate-500 disabled:hover:scale-100 transition-all rounded-full text-white shadow-md shadow-blue-500/20 cursor-pointer ${
              isDemo ? 'right-1.5' : 'left-1.5'
            }`}
          >
            <Send className={`w-3.5 h-3.5 ${isDemo ? '' : '-scale-x-100'} transform`} />
          </button>
        </div>
      </div>
    </div>
  );
};
