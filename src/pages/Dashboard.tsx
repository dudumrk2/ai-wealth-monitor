 import React from 'react'; 
import DashboardLayout from '../components/layout/DashboardLayout';
import ActionItems from '../components/dashboard/ActionItems';
import AssetTable from '../components/dashboard/AssetTable';
import { MOCK_DATA } from '../data/mockData';
import { Wallet, PieChart, Activity } from 'lucide-react';
import clsx from 'clsx';

type TabView = 'user' | 'spouse' | 'joint';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabView>('user');
  
  // Handlers for mock data properties
  const userPortfolio = MOCK_DATA.portfolios.user;
  const spousePortfolio = MOCK_DATA.portfolios.spouse;
  const jointPortfolio = MOCK_DATA.portfolios.joint;

  const renderTabContent = () => {
    switch(activeTab) {
      case 'user':
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
             <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
               {/* Quick Stats Cards */}
               <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                  <div className="p-3 bg-blue-50 text-blue-600 rounded-xl"><Wallet /></div>
                  <div>
                    <p className="text-sm font-semibold text-slate-500">Total Pension</p>
                    <p className="text-2xl font-bold text-slate-900">₪450,200</p>
                  </div>
               </div>
               <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                  <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl"><PieChart /></div>
                  <div>
                    <p className="text-sm font-semibold text-slate-500">Study Funds (Keren Hishtalmut)</p>
                    <p className="text-2xl font-bold text-slate-900">₪125,000</p>
                  </div>
               </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                  <div className="p-3 bg-purple-50 text-purple-600 rounded-xl"><Activity /></div>
                  <div>
                    <p className="text-sm font-semibold text-slate-500">Alt. Investments</p>
                    <p className="text-2xl font-bold text-slate-900">₪85,000</p>
                  </div>
               </div>
             </div>

             <AssetTable title="Active Pension Funds" funds={userPortfolio.pension_funds} />
             <AssetTable title="Study Funds" funds={userPortfolio.study_funds} />
             
             {/* Alternative Investments Card */}
             <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
               <div className="p-5 border-b border-slate-100"><h3 className="font-bold text-lg text-slate-800">Alternative Investments</h3></div>
               <div className="p-5 space-y-4">
                  {userPortfolio.alternative_investments.map(alt => (
                    <div key={alt.id} className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-100">
                      <div>
                        <h4 className="font-semibold text-slate-900">{alt.name}</h4>
                        <p className="text-sm text-slate-500">{alt.description}</p>
                      </div>
                      <div className="mt-4 md:mt-0 text-right">
                         <div className="text-lg font-bold text-slate-900">₪{alt.balance.toLocaleString()}</div>
                         <div className="text-sm font-medium text-emerald-600">Expected Yield: {alt.expected_yearly_yield}% / Yr</div>
                      </div>
                    </div>
                  ))}
               </div>
             </div>
          </div>
        );
      case 'spouse':
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
             <div className="flex items-center gap-4 p-6 bg-gradient-to-r from-blue-50 to-emerald-50 rounded-2xl border border-blue-100 mb-8">
                 <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm text-blue-600"><PieChart /></div>
                 <div>
                   <h3 className="text-lg font-bold text-blue-900">Spouse's Aggregated Wealth</h3>
                   <p className="text-blue-700/80 text-sm font-medium">Synced securely via separate Google Login mapping.</p>
                 </div>
             </div>
             <AssetTable title="Active Pension Funds" funds={spousePortfolio.pension_funds} />
          </div>
        );
      case 'joint':
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-slate-900 text-white p-8 rounded-3xl shadow-xl relative overflow-hidden mb-8">
               <div className="absolute right-0 bottom-0 w-64 h-64 bg-blue-500/20 rounded-full blur-3xl translate-x-1/2 translate-y-1/2"></div>
               <h2 className="text-3xl font-bold tracking-tight mb-2">₪{jointPortfolio.total_family_wealth.toLocaleString()}</h2>
               <p className="text-slate-400 font-medium tracking-wide text-sm uppercase">Total Family Household Wealth</p>
            </div>
            {/* Needs chart lib for optimal display, placeholders for now */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
               <div className="bg-white p-6 rounded-2xl border border-slate-200">
                 <h3 className="font-bold text-slate-800 mb-4 text-lg">Asset Allocation</h3>
                 <div className="space-y-4">
                   <div className="flex items-center justify-between text-sm font-semibold"><span className="text-slate-600">Stocks</span> <span className="text-slate-900">{jointPortfolio.asset_allocation_percentages.stocks}%</span></div>
                   <div className="w-full bg-slate-100 rounded-full h-2.5"><div className="bg-blue-600 h-2.5 rounded-full" style={{ width: `${jointPortfolio.asset_allocation_percentages.stocks}%` }}></div></div>
                   
                   <div className="flex items-center justify-between text-sm font-semibold pt-2"><span className="text-slate-600">Bonds</span> <span className="text-slate-900">{jointPortfolio.asset_allocation_percentages.bonds}%</span></div>
                   <div className="w-full bg-slate-100 rounded-full h-2.5"><div className="bg-emerald-500 h-2.5 rounded-full" style={{ width: `${jointPortfolio.asset_allocation_percentages.bonds}%` }}></div></div>
                 </div>
               </div>
               <div className="bg-white p-6 rounded-2xl border border-slate-200">
                  <h3 className="font-bold text-slate-800 mb-4 text-lg">Provider Exposure</h3>
                  <div className="space-y-3">
                     {Object.entries(jointPortfolio.provider_exposure).map(([provider, value]) => (
                        <div key={provider} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg text-sm font-semibold">
                          <span className="text-slate-700">{provider}</span>
                          <span className="text-slate-900">{value as number}%</span>
                        </div>
                     ))}
                  </div>
               </div>
            </div>
          </div>
        );
    }
  };

  return (
    <DashboardLayout>
      <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
           <h1 className="text-3xl font-bold tracking-tight text-slate-900">Portfolio Overview</h1>
           <p className="text-slate-500 mt-1">Track, analyze, and optimize your family's future.</p>
        </div>
      </div>

      <div className="flex flex-col xl:flex-row gap-8">
        
        {/* Main Tabs Column */}
        <div className="flex-1 min-w-0">
          
          <div className="bg-slate-200/50 p-1 rounded-xl inline-flex mb-6 overflow-x-auto max-w-full">
            {(['user', 'spouse', 'joint'] as const).map(tab => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={clsx(
                  "px-6 py-2.5 rounded-lg text-sm font-bold transition-all whitespace-nowrap",
                  activeTab === tab 
                    ? "bg-white text-slate-900 shadow-sm" 
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                {tab === 'user' && "My Portfolio"}
                {tab === 'spouse' && "Spouse Portfolio"}
                {tab === 'joint' && "Joint View"}
              </button>
            ))}
          </div>

          {renderTabContent()}

        </div>

        {/* Action Items Sidebar */}
        <div className="xl:w-80 shrink-0">
           <ActionItems />
        </div>

      </div>
    </DashboardLayout>
  );
}
