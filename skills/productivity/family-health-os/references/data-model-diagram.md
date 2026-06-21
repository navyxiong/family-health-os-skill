# Family Health OS schema diagram

This diagram shows the entity relationships for the memory data layer.
```

┌─────────────────────────────────────────────────────────────────┐
│                        patients.json                            │
│  id (PK) · name · gender · birthDate · bloodType · allergies[]  │
│  emergencyContact · familyHistory[] · lifestyle · tags[]        │
└────────┬────────┬────────┬────────────┬──────────┬──────────────┘
         │        │        │            │          │
         │        │ ░░░░░░░│░░░░░░░░░░░░│░░░░░░░░░░│
         │        │        ▼            ▼          ▼
         │        │  ┌──────────────────────────────┐
         │        │  │      diseases.json            │
         │        │  │  id (PK) · patientId (FK)    │
         │        │  │  diseaseName · icdCode        │
         │        │  │  episodes[] · complications[]│
         │        │  │  targetValues · medications[]│
         │        │  └───────────┬──────────────────┘
         │        │              │
         │        ▼              ▼
         │  ┌──────────────────────────────────────────┐
         │  │           exams.json                      │
         │  │  id (PK) · patientId (FK)                │
         │  │  examDate · examType · items[] (↑↓)      │
         │  │  images[] · relatedDiseaseIds[]          │
         │  │  relatedHospitalizationId                │
         │  └──────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                  medications.json                    │
│  id (PK) · patientId (FK) · medicationName          │
│  dosage · frequency · sideEffects[]                  │
│  isOngoing · relatedDiseaseIds[]                     │
│  relatedHospitalizationId                            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      hospitalizations.json                           │
│  id (PK) · patientId (FK) · admissionDate · dischargeDate           │
│  dailyProgress[] (dailyProgress/roundNote/consultationNote/...)     │
│  surgeries[] · consultations[] · dischargeSummary · followUpPlan    │
└──────────────────────────────────────────────────────────────────────┘
         │                                                   │
         │                                                   │
         ▼                                                   ▼
┌──────────────────────────────────────────────────────────────┐
│           timeline.json                                       │
│  id (PK) · patientId (FK)                                    │
│  events[] (29 types × 9 categories)                          │
│    ├ eventId · date · eventType · category                   │
│    ├ title · description · severity · isKeyEvent             │
│    ├ sourceType · sourceId · sourceDoctor · sourceInstitution│
│    ├ metadata{value,unit,flag} · affectedBodySite            │
│    └ tags[] · relatedEventIds[]                              │
│  monthlyGroups (YYYY-MM)  ·  eventTypeCategoryMap{}          │
│  summary · eventCount · dateRange · version                  │
└──────────────────────────────────────────────────────────────┘

Legend: PK = 主键 (UUID v4)  FK = 外键引用
```
