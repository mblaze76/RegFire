# Demographics setup

The Demographics page has an organizer question editor and a clearly separate **Demographics website preview** area. The preview renders unsaved questions, RegType visibility and branching without collecting attendee records. **Open live preview ↗** opens a dedicated demographics-only window, without the registration/contact form above it.

Create short text, long text, single choice, multiple choice, dropdown, number, date or yes/no questions. Each has a label, optional help, a required-when-visible flag, and a stable ID. Choice labels have stable option IDs, so renaming a choice preserves its rules. Duplicate creates fresh question/option IDs. Remove, up/down controls and pointer drag change the definition. Nothing is required by default.

**RegType assignment** is prominent on every question: choose all types, or any nonempty selection. One question can be shared by several RegTypes. The question must match its RegType assignment AND its branching rules.

Rules reference earlier questions only; choose all or any rules. Text supports equality, inequality, contains and answered; choices support equality/inequality; multi-choice supports includes/not-includes; numbers and dates support comparisons; yes/no supports equality/inequality. Unanswered or hidden sources do not satisfy even negative conditions. Hidden answers are excluded from downstream evaluation and hidden required questions do not block the preview.

Deletion of referenced questions and referenced options is blocked until rules are adjusted. Compatible question-type changes (single choice ↔ dropdown, short ↔ long text) preserve branching and choice identities immediately. An incompatible type change explicitly confirms any non-answer-presence rules that must become “Is answered” and any removed answer-choice list. Cancel preserves the original type and rules. Follow-up questions are retained. Reordering cannot move a source after its dependent. Saving registration settings cannot remove a RegType referenced by saved demographics. Save/reload and application restart retain event-specific definitions in PostgreSQL. Preview answers are never stored.

Limits: 50 questions, 30 options per choice question, 10 rules per question. The optional demo questions concern professional interests. No sensitive mandatory defaults are imposed.
