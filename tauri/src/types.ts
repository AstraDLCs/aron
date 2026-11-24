// Espejo del "Contrato de la foto" (GET /api/state) de la API FastAPI.

export type AppSection =
  | 'candidatos'
  | 'organigrama'
  | 'requerimientos'
  | 'carpeta'
  | 'psicologicas'
  | 'procesos'
  | 'reportes'
  | 'bitacora'
  | 'configuracion';

export type JobUrgency = 'Urgente' | 'Media' | 'Planificada';

export type CandidateDecision = 'Pendiente de revisión' | 'Aprobado' | 'Rechazado' | 'Contratado';

export type AiVerdict = 'Pre-aprobado' | 'Pre-denegado';

export type AiStatus = 'En cola' | 'Procesando' | 'Clasificado' | 'Error IA' | 'Sin texto' | 'Sin IA';

export type RequirementStatus = 'Abierto' | 'Cubierto' | 'Cancelado';

export type SourceCategory = 'Portal Minero' | 'Red Profesional' | 'Bolsa Nacional' | 'Referidos Faena';

export type TestCategory = 'Psicolaboral' | 'Técnica Minera' | 'Seguridad HSEC' | 'Operación / Maquinaria';

export type CvOrigin = 'app' | 'importacion' | 'sync_local' | 'carpeta_servidor';

export type PsychTestStatus = 'Sin enviar' | 'Enviada' | 'Completada';

export type PsychAptitudeLevel = 'Pendiente' | 'Apto Recomendado' | 'Apto con Observación' | 'Requiere Entrevista';

export interface UserOut {
  id: string;
  fullName: string;
  email: string;
  jobTitle: string;
  isActive: boolean;
}

export interface AppSettings {
  companyName: string;
  aiModel: string;
  aiFallbackModels: string[];
  aiPreapproveThreshold: number;
  aiEnabled: boolean;
  aiConfigured: boolean;
}

export interface AiQueueStatus {
  queued: number;
  processing: number;
  errors: number;
  sinIa: number;
  pausedUntil: string | null;
  aiEnabled: boolean;
  model: string;
  /** Qué está haciendo el worker y cuándo dio señales (servidores anteriores a la 0.2.4 no lo envían). */
  workerSeenAt?: string | null;
  workerStatus?: string;
  nextAttemptAt?: string | null;
  lastError?: string | null;
}

export interface Position {
  id: string;
  name: string;
  folderName: string;
  area: string;
  parentId: string | null;
  description: string;
  requiredSkills: string;
  technicalSpecifications: string;
  minYearsExperience: number;
  educationProfile: string;
  sortOrder: number;
  openRequirementsCount: number;
  candidatesCount: number;
}

export interface JobNeed {
  id: string;
  positionId: string;
  title: string;
  department: string;
  urgency: JobUrgency;
  vacancies: number;
  filledCount: number;
  requiredSkills: string;
  technicalSpecifications: string;
  companyContext: string;
  publishedBoards: string[];
  publishedSourceIds: string[];
  openedAt: string;
  targetDaysToFill: number;
  createdBy: string;
  status: RequirementStatus;
  extraSkills: string;
}
export type Requirement = JobNeed;

export interface JobBoardChannel {
  id: string;
  name: string;
  folderName: string;
  category: SourceCategory;
  proposalsSent: number;
  candidatesReceived: number;
  shortlistedCount: number;
  hiredCount: number;
  avgResponseHours: number;
  lastProposalAt: string | null;
  active: boolean;
}
export type Source = JobBoardChannel;

export interface PsychTestScores {
  estabilidadEmocional: number;
  toleranciaFaenaAltura: number;
  apegoSeguridadHSEC: number;
  trabajoEquipo: number;
  razonamientoOperativo: number;
}

export interface PsychEvaluation {
  testBatteryName: string;
  accessCode: string;
  status: PsychTestStatus;
  sentAt?: string;
  sentBy?: string;
  completedAt?: string;
  durationSeconds?: number;
  scores: PsychTestScores | null;
  averageScore: number | null;
  aptitudeLevel: PsychAptitudeLevel;
  aiPsychObservation: string;
}

export interface CandidateMetricReport {
  technicalSpecsScore: number;
  experienceScore: number;
  educationCareerScore: number;
  psychScore: number;
  overallScore: number;
  fitVerdict: string;
  aiDetailedReport: string;
  generatedAt: string;
}

export interface ExcelTestParsedRow {
  item: string;
  answer: string;
  score: number;
  concrete: boolean;
}

export interface ExcelTestResult {
  id: string;
  testId?: string;
  testName: string;
  fileName: string;
  uploadedAt: string;
  totalQuestions: number;
  answeredCount: number;
  autoComputedScore: number;
  isConcreteResult: boolean;
  concreteVerdict: 'Resultados Concretos' | 'Resultados Parciales' | 'Inconsistencia Detectada';
  aiAnalysis: string;
  parsedRows: ExcelTestParsedRow[];
  passingScore?: number | null;
  passed?: boolean | null;
}

export interface TestDefinition {
  id: string;
  name: string;
  category: TestCategory;
  targetArea: string;
  durationMinutes: number;
  questions: string[];
  passingScore: number;
  sourceFileName?: string;
  createdBy: string;
  createdAt: string;
}

export interface AiChatMessage {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  createdAt: string;
  vote?: 'up' | 'down' | null;
  feedbackNote?: string;
}

export interface AiReportConversation {
  id: string;
  candidateId: string;
  candidateName: string;
  title: string;
  createdAt: string;
  messages: AiChatMessage[];
  structuredReport?: {
    recommendation: string;
    strengths: string[];
    watchouts: string[];
    concreteSummary?: string;
  };
}

export interface OtherApplication {
  candidateId: string;
  positionName: string;
  decision: CandidateDecision;
}

export interface Candidate {
  id: string;
  personId: string;
  cvFileId: string | null;
  positionId: string;
  requirementId: string | null;
  targetNeedId: string;
  targetRoleTitle: string;
  sourceBoardId: string;
  sourceBoardName: string;
  fullName: string;
  firstNames: string;
  lastNames: string;
  documentId: string;
  email: string;
  phone: string;
  phoneOrEmail: string;
  age: number | null;
  originLocation: string;
  university: string;
  career: string;
  yearsWorked: number | null;
  workHistorySummary: string;
  specifications: string[];
  languages: string[];
  licenses: string[];
  interviewNotes: string;
  cvFileName?: string;
  cvMimeType?: string;
  cvUploadedAt?: string;
  cvUploadedBy?: string;
  cvOrigin?: CvOrigin | string;
  cvPath?: string;
  cvMissing: boolean;
  psychEvaluation: PsychEvaluation;
  excelTestResults: ExcelTestResult[];
  metricReport: CandidateMetricReport;
  aiStatus: AiStatus;
  aiVerdict: AiVerdict | null;
  aiAptitudeScore: number | null;
  aiStrengths: string[];
  aiObservations: string[];
  aiReason: string;
  aiAppliedCriteria: string[];
  aiAppliedCorrectionTitle?: string;
  aiModel: string | null;
  aiClassifiedAt: string | null;
  aiError: string | null;
  aiSummary: string;
  aiObservedScore: number;
  decision: CandidateDecision;
  managerScore: number | null;
  managerNotes: string;
  evaluatedBy?: string;
  evaluatedAt?: string;
  possibleSamePersonIds: string[];
  otherApplications: OtherApplication[];
  processDaysElapsed: number;
  createdAt: string;
}

export interface BlockedCvFile {
  id: string;
  sha256: string;
  positionId: string;
  originalName: string;
  deletedBy: string;
  deletedAt: string;
}

export interface RecruitmentCriterion {
  id: string;
  title: string;
  appliesToDepartment: string;
  weightLabel: 'Prioritario' | 'Importante' | 'Deseable';
  ruleText: string;
  isCorrection?: boolean;
  wrongAiAssumption?: string;
  learnedFromCandidate?: string;
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
}

export interface RecruitmentKPIs {
  totalVacancies: number;
  filledVacancies: number;
  remainingVacancies: number;
  coveragePercent: number;
  totalCandidates: number;
  preselectedOrHired: number;
  psychCompletedCount: number;
  psychPendingCount: number;
  avgProcessDays: number;
  totalProposalsSent: number;
  topBoardName: string;
  topBoardCandidates: number;
  aiAgreementRate: number;
}

export interface AppState {
  catalogVersion: number;
  companyName: string;
  hrChiefName: string;
  hrChiefTitle: string;
  currentUser: UserOut;
  settings: AppSettings;
  aiQueue: AiQueueStatus;
  positions: Position[];
  jobNeeds: JobNeed[];
  jobBoards: JobBoardChannel[];
  candidates: Candidate[];
  blockedCvFiles: BlockedCvFile[];
  recruitmentCriteria: RecruitmentCriterion[];
  testCatalog: TestDefinition[];
  aiConversations: AiReportConversation[];
  kpis: RecruitmentKPIs;
}

export interface StateResponse {
  state: AppState;
}

export interface ModuleProps {
  state: AppState;
  onState: (s: AppState) => void;
  refresh: () => Promise<void>;
  navigate: (section: AppSection, opts?: { candidateId?: string; positionId?: string }) => void;
}

export interface DataCenterStatus {
  mode: string;
  storagePath: string;
  totalRecords: number;
  candidatesCount: number;
  vacanciesCount: number;
  boardsCount: number;
  criteriaCount: number;
  psychCompletedCount: number;
  lastSavedAt: string;
  [k: string]: unknown;
}

export interface AuditEntry {
  id: string;
  at: string;
  actorId: string | null;
  actorName: string;
  action: string;
  entityType: string;
  entityId: string | null;
  summary: string;
  details?: unknown;
  [k: string]: unknown;
}
