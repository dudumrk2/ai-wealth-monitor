export interface AltProject {
  id?: string;
  name: string;
  developer: string;
  originalAmount: number;
  currency: string;
  startDate: string; // ISO string like "2023-11-20"
  durationMonths: number;
  expectedReturn: number;
  status: 'Active' | 'Exited';
  actualExitDate?: string;
  finalAmount?: number;
  pdfUrl?: string; // Uploaded project presentation / document
}

export interface LeveragedPolicy {
  id?: string;
  policyNumber: string;
  name: string;
  funderLink: string;
  currentBalance: number;
  baseMonth: string; // Like "2023-11"
  balloonLoanAmount: number;
  interestRate: number;
  initialDepositAmount: number;
  initialRepaymentDate: string;
  pdfUrl?: string;
}
