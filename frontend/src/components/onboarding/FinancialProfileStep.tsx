import React, { useState, useEffect } from 'react';

interface FinancialData {
  spouse1BirthYear: string;
  spouse2BirthYear: string;
  kidsCount: number;
  childrenBirthYears: string[];
  investmentGoal: string;
  riskTolerance: string;
}

interface FinancialProfileStepProps {
  onComplete: (data: any) => void;
  initialData?: Partial<FinancialData>;
  onDataChange?: (data: Partial<FinancialData>) => void;
}

const FinancialProfileStep: React.FC<FinancialProfileStepProps> = ({ onComplete, initialData, onDataChange }) => {
  const currentYear = new Date().getFullYear();

  const [birthYears, setBirthYears] = useState({
    spouse1: initialData?.spouse1BirthYear || '1984',
    spouse2: initialData?.spouse2BirthYear || '1986'
  });
  const [kidsCount, setKidsCount] = useState(initialData?.kidsCount ?? 3);
  const [childrenBirthYears, setChildrenBirthYears] = useState<string[]>(
    initialData?.childrenBirthYears || ['2008', '2011', '2014']
  );
  const [preferences, setPreferences] = useState({
    investmentGoal: initialData?.investmentGoal || 'growth',
    riskTolerance: initialData?.riskTolerance || 'high'
  });

  // Notify parent of changes for persistence
  useEffect(() => {
    if (onDataChange) {
      onDataChange({
        spouse1BirthYear: birthYears.spouse1,
        spouse2BirthYear: birthYears.spouse2,
        kidsCount,
        childrenBirthYears,
        investmentGoal: preferences.investmentGoal,
        riskTolerance: preferences.riskTolerance
      });
    }
  }, [birthYears, kidsCount, childrenBirthYears, preferences, onDataChange]);

  const handleChildYearChange = (index: number, value: string) => {
    const newYears = [...childrenBirthYears];
    newYears[index] = value;
    setChildrenBirthYears(newYears);
  };

  const handleKidsCountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const count = parseInt(e.target.value) || 0;
    setKidsCount(count);
    
    const newYears = [...childrenBirthYears];
    if (count > childrenBirthYears.length) {
      newYears.push(...Array(count - childrenBirthYears.length).fill(''));
    } else {
      newYears.splice(count);
    }
    setChildrenBirthYears(newYears);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const profileData = {
      spouse_1_birth_year: parseInt(birthYears.spouse1),
      spouse_2_birth_year: parseInt(birthYears.spouse2),
      number_of_children: kidsCount,
      children_birth_years: childrenBirthYears.map(year => parseInt(year) || 0),
      investment_preference: preferences.investmentGoal,
      risk_tolerance: preferences.riskTolerance
    };
    onComplete(profileData);
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-sm mt-8 border border-gray-100 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-blue-600 text-white p-6 rounded-t-lg -mt-6 -mx-6 mb-6">
        <h2 className="text-2xl font-bold text-center">פרופיל פיננסי ומשפחתי</h2>
        <p className="text-center text-blue-100 mt-2">שלב 2 מתוך 2 — התאמה אישית של מנוע ה-AI</p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="spouse1BirthYear" className="block text-sm font-medium text-gray-700 mb-1">שנת לידה בן/בת זוג 1</label>
            <input 
              id="spouse1BirthYear"
              type="number" 
              name="spouse1BirthYear"
              min="1900" 
              max={currentYear} 
              value={birthYears.spouse1} 
              onChange={(e) => setBirthYears({...birthYears, spouse1: e.target.value})} 
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" 
              required 
              autoComplete="bday-year"
            />
          </div>
          <div>
            <label htmlFor="spouse2BirthYear" className="block text-sm font-medium text-gray-700 mb-1">שנת לידה בן/בת זוג 2</label>
            <input 
              id="spouse2BirthYear"
              type="number" 
              name="spouse2BirthYear"
              min="1900" 
              max={currentYear} 
              value={birthYears.spouse2} 
              onChange={(e) => setBirthYears({...birthYears, spouse2: e.target.value})} 
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500" 
              autoComplete="bday-year"
            />
          </div>
        </div>
        <div className="border-t border-gray-100 pt-6">
          <label htmlFor="kidsCount" className="block text-sm font-medium text-gray-700 mb-1">מספר ילדים</label>
          <input 
            id="kidsCount"
            type="number" 
            name="kidsCount"
            min="0" 
            value={kidsCount} 
            onChange={handleKidsCountChange} 
            className="w-full md:w-1/3 p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 mb-4" 
          />
          {kidsCount > 0 && (
            <div className="grid grid-cols-3 md:grid-cols-4 gap-3 bg-gray-50 p-4 rounded-md">
              {childrenBirthYears.map((year, index) => (
                <div key={index}>
                  <label htmlFor={`childYear${index}`} className="block text-xs text-gray-500 mb-1">שנת לידה ילד {index + 1}</label>
                  <input 
                    id={`childYear${index}`}
                    type="number" 
                    name={`childYear${index}`}
                    min="1980" 
                    max={currentYear} 
                    value={year} 
                    onChange={(e) => handleChildYearChange(index, e.target.value)} 
                    className="w-full p-2 border border-gray-300 rounded-md text-sm" 
                    required 
                  />
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-gray-100 pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label htmlFor="investmentGoal" className="block text-sm font-medium text-gray-700 mb-1">העדפת השקעה</label>
            <select id="investmentGoal" name="investmentGoal" value={preferences.investmentGoal} onChange={(e) => setPreferences({...preferences, investmentGoal: e.target.value})} className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
              <option value="solid">שמירה על הקיים (סולידי)</option>
              <option value="balanced">צמיחה מתונה (מאוזן)</option>
              <option value="growth">מיקסום תשואה (צמיחה)</option>
            </select>
          </div>
          <div>
            <label htmlFor="riskTolerance" className="block text-sm font-medium text-gray-700 mb-1">רמת סיכון מבוקשת</label>
            <select id="riskTolerance" name="riskTolerance" value={preferences.riskTolerance} onChange={(e) => setPreferences({...preferences, riskTolerance: e.target.value})} className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
              <option value="low">נמוכה</option>
              <option value="medium">בינונית</option>
              <option value="high">גבוהה</option>
            </select>
          </div>
        </div>
        <div className="pt-6">
          <button type="submit" className="w-full bg-blue-600 text-white font-medium py-3 px-4 rounded-md hover:bg-blue-700 transition duration-200 shadow-md">שמור והמשך לדאשבורד</button>
        </div>
      </form>
    </div>
  );
};

export default FinancialProfileStep;
