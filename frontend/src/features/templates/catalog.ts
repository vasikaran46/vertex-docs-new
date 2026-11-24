// Editable document templates. Each builder returns pre-filled HTML (realistic sample content, personalised with
// the signed-in user's name/email) that is edited directly on the page. Colours come from --tpl-accent.

export type TemplateCategory = 'Resume & CV' | 'Letters' | 'Certificates' | 'Business' | 'Education & Events';
export type Ctx = { name: string; email: string; date: string };
export type TemplateItem = { id: string; category: TemplateCategory; name: string; description: string; ats?: boolean; accent: string; font: string; build: (c: Ctx) => string };

const AC = 'var(--tpl-accent)';
const pad = (inner: string, p = '48px 56px') => `<div style="padding:${p}">${inner}</div>`;
const h = (t: string, size = 13) => `<div style="font-size:${size}px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:${AC};border-bottom:1.5px solid ${AC};padding-bottom:3px;margin:18px 0 8px">${t}</div>`;
const li = (items: string[]) => `<ul style="margin:0 0 6px;padding-left:1.3em">${items.map((i) => `<li>${i}</li>`).join('')}</ul>`;
const job = (role: string, org: string, when: string, bullets: string[]) =>
  `<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;gap:12px"><b>${role}</b><span>${when}</span></div><div style="font-style:italic;margin-bottom:3px">${org}</div>${li(bullets)}</div>`;
const sig = (name: string, role = '') => `<div style="margin-top:46px"><div style="width:190px;border-top:1px solid #333;padding-top:4px"><b>${name}</b>${role ? `<br>${role}` : ''}</div></div>`;
const letterHead = (c: Ctx) => `<div style="border-bottom:3px solid ${AC};padding-bottom:10px;margin-bottom:26px"><div style="font-size:24px;font-weight:700;color:${AC}">Your Company Name Pvt. Ltd.</div><div style="font-size:12px;color:#555">12, Business Park Road, Coimbatore, Tamil Nadu 641001 · +91 98765 43210 · hr@yourcompany.com</div></div>`;
const cert = (title: string, body: string, c: Ctx) => `<div style="margin:34px;padding:44px 40px;border:6px double ${AC};text-align:center;min-height:900px"><div style="font-size:15px;letter-spacing:.3em;color:${AC}">YOUR COMPANY NAME PVT. LTD.</div><div style="font-size:38px;font-weight:700;margin:26px 0 8px;font-family:Georgia,serif">${title}</div><div style="width:120px;height:3px;background:${AC};margin:0 auto 30px"></div><div style="font-size:15px;line-height:2;text-align:justify">${body}</div><div style="display:flex;justify-content:space-between;margin-top:90px;text-align:center"><div><div style="width:170px;border-top:1px solid #333;padding-top:4px">Date: ${c.date}</div></div><div><div style="width:190px;border-top:1px solid #333;padding-top:4px"><b>Authorised Signatory</b><br>HR Manager</div></div></div></div>`;

const resumeContact = (c: Ctx) => `${c.email} · +91 98765 43210 · Coimbatore, Tamil Nadu · linkedin.com/in/${c.name.toLowerCase().replace(/[^a-z]+/g, '')}`;
const skills = ['Python, JavaScript, TypeScript, SQL', 'React, FastAPI, REST APIs, Git', 'PostgreSQL, Docker, Render deployment', 'Problem solving, teamwork, communication'];

const experienceBullets = [
  'Built and shipped a document-management web app used by 2,000+ users, cutting manual processing time by 40%.',
  'Reduced average API response time from 900 ms to 250 ms by adding caching and query optimisation.',
  'Led a team of 4 interns; introduced code reviews and automated tests that raised coverage to 85%.',
];

export const templateCatalog: TemplateItem[] = [
  {
    id: 'resume-ats-classic', category: 'Resume & CV', name: 'ATS Classic Resume', ats: true, accent: '#1f3a5f', font: 'Arial',
    description: 'Single column, standard headings and plain bullets. The safest layout for applicant tracking systems.',
    build: (c) => pad(`<div style="text-align:center"><div style="font-size:30px;font-weight:700">${c.name}</div><div style="font-size:12px;margin-top:4px">${resumeContact(c)}</div></div>
${h('Professional Summary')}<div>Results-driven software developer with 3+ years of experience building web applications with React and Python. Strong record of improving performance, shipping on schedule and collaborating with cross-functional teams.</div>
${h('Skills')}${li(skills)}
${h('Professional Experience')}${job('Software Developer', 'JM Vertex Technologies, Coimbatore', 'Jun 2023 – Present', experienceBullets)}${job('Software Developer Intern', 'TechNova Solutions, Chennai', 'Jan 2023 – May 2023', ['Developed 12 reusable UI components in React, reducing page build time by 30%.', 'Wrote unit tests and fixed 45+ bugs across two releases.'])}
${h('Education')}<div style="display:flex;justify-content:space-between"><b>B.E. Computer Science and Engineering</b><span>2019 – 2023</span></div><div>Anna University, Tamil Nadu · CGPA 8.7 / 10</div>
${h('Projects')}${li(['<b>Vertex Docs</b> – PDF, translation and AI document workspace (React, FastAPI, PostgreSQL).', '<b>Smart Attendance</b> – face-recognition attendance system with 96% accuracy (Python, OpenCV).'])}
${h('Certifications')}${li(['AWS Certified Cloud Practitioner – 2024', 'Meta Front-End Developer Professional Certificate – 2023'])}`),
  },
  {
    id: 'resume-modern', category: 'Resume & CV', name: 'Modern Professional Resume', ats: true, accent: '#6a3df0', font: 'Calibri',
    description: 'Coloured header band with a clean single-column body. Stylish and still ATS-friendly.',
    build: (c) => `<div style="background:${AC};color:#fff;padding:38px 56px"><div style="font-size:34px;font-weight:700">${c.name}</div><div style="font-size:15px;opacity:.92">Full-Stack Software Developer</div><div style="font-size:12px;margin-top:8px;opacity:.92">${resumeContact(c)}</div></div>${pad(`
${h('Profile')}<div>Full-stack developer who turns complex workflows into simple, fast products. Comfortable across the stack, from React interfaces to Python APIs and cloud deployment.</div>
${h('Experience')}${job('Software Developer', 'JM Vertex Technologies', '2023 – Present', experienceBullets)}
${h('Skills')}<div>${skills.join(' &nbsp;•&nbsp; ')}</div>
${h('Education')}<div><b>B.E. Computer Science</b> · Anna University · 2023 · CGPA 8.7</div>
${h('Achievements')}${li(['Winner – State-level hackathon 2024 (team of 4).', 'Published 2 technical articles with 15k+ reads.'])}`, '10px 56px 48px')}`,
  },
  {
    id: 'resume-sidebar', category: 'Resume & CV', name: 'Two-Column Sidebar Resume', accent: '#0f766e', font: 'Segoe UI',
    description: 'Coloured sidebar for contact and skills, main column for experience. Best for design-forward roles.',
    build: (c) => `<div style="display:flex;min-height:1060px"><div style="width:31%;background:${AC};color:#fff;padding:44px 24px"><div style="font-size:26px;font-weight:700;line-height:1.15">${c.name}</div><div style="margin:6px 0 24px;opacity:.9">Product Designer</div><div style="font-weight:700;letter-spacing:.1em;margin-bottom:6px">CONTACT</div><div style="font-size:12px;line-height:1.8">${c.email}<br>+91 98765 43210<br>Coimbatore, India<br>portfolio.com/${c.name.split(' ')[0].toLowerCase()}</div><div style="font-weight:700;letter-spacing:.1em;margin:24px 0 6px">SKILLS</div><div style="font-size:12px;line-height:1.9">Figma · UI/UX design<br>Design systems<br>Prototyping<br>HTML &amp; CSS<br>User research</div><div style="font-weight:700;letter-spacing:.1em;margin:24px 0 6px">LANGUAGES</div><div style="font-size:12px;line-height:1.9">English · Tamil · Hindi</div></div><div style="flex:1;padding:44px 36px">${h('About me')}<div>Designer with 4 years of experience creating accessible, conversion-focused interfaces for fintech and SaaS products.</div>${h('Experience')}${job('Senior UI/UX Designer', 'Pixel Labs, Bengaluru', '2022 – Present', ['Redesigned onboarding flow, lifting activation by 27%.', 'Built a design system of 80+ components used by 3 product teams.'])}${job('UI Designer', 'Brightside Studio', '2020 – 2022', ['Delivered 15+ websites and mobile app designs for startups.'])}${h('Education')}<div><b>B.Des – Communication Design</b><br>NIFT · 2020</div></div></div>`,
  },
  {
    id: 'resume-fresher', category: 'Resume & CV', name: 'Fresher / Entry-Level Resume', ats: true, accent: '#2563eb', font: 'Arial',
    description: 'Education and projects first, built for students and first-time job seekers.',
    build: (c) => pad(`<div style="font-size:28px;font-weight:700;color:${AC}">${c.name}</div><div style="font-size:12px;margin-top:2px">${resumeContact(c)}</div>
${h('Career Objective')}<div>Motivated Computer Science graduate seeking an entry-level software role to apply strong fundamentals in programming, databases and web development while growing with a collaborative team.</div>
${h('Education')}<div style="display:flex;justify-content:space-between"><b>B.Tech Information Technology</b><span>2022 – 2026</span></div><div>Government College of Technology · CGPA 8.4 / 10</div><div style="display:flex;justify-content:space-between;margin-top:6px"><b>Higher Secondary (HSC)</b><span>2022</span></div><div>Sri Vidya Matric Higher Secondary School · 92%</div>
${h('Projects')}${li(['<b>Online Examination Portal</b> – role-based exam system with auto grading (React, Node.js, MongoDB).', '<b>Weather Forecast App</b> – responsive app using public APIs and charts.', '<b>Library Management System</b> – Java + MySQL desktop application.'])}
${h('Technical Skills')}${li(['Languages: Java, Python, JavaScript, SQL', 'Web: HTML, CSS, React, Node.js', 'Tools: Git, VS Code, Postman'])}
${h('Internship')}${job('Web Development Intern', 'CodeCraft Technologies', 'Jun 2025 – Jul 2025', ['Built 5 responsive pages and integrated REST APIs.', 'Fixed 20+ UI bugs and improved page load speed by 25%.'])}
${h('Achievements & Activities')}${li(['Finalist – Smart India Hackathon 2025.', 'Coordinator – College technical symposium (400+ participants).'])}`),
  },
  {
    id: 'resume-executive', category: 'Resume & CV', name: 'Executive CV', accent: '#7c2d12', font: 'Georgia',
    description: 'Elegant serif layout with a career highlights block for senior roles.',
    build: (c) => pad(`<div style="border-bottom:2px solid ${AC};padding-bottom:12px"><div style="font-size:32px;font-weight:700;letter-spacing:.02em">${c.name}</div><div style="font-size:15px;color:${AC};margin-top:2px">Head of Operations · MBA</div><div style="font-size:12px;margin-top:6px">${resumeContact(c)}</div></div>
${h('Executive Summary')}<div>Operations leader with 12+ years of experience scaling teams and processes across manufacturing and logistics. Proven ability to cut costs, improve delivery and build high-performing teams.</div>
${h('Career Highlights')}${li(['Reduced operating costs by ₹4.2 crore (18%) through vendor consolidation and automation.', 'Scaled the workforce from 40 to 220 while improving on-time delivery to 97%.', 'Led ERP rollout across 6 sites, on time and within budget.'])}
${h('Professional Experience')}${job('Head of Operations', 'Sunrise Industries Ltd., Coimbatore', '2019 – Present', ['Own P&L of ₹120 crore across 6 plants and 3 warehouses.', 'Report to the CEO; manage 8 direct reports and 220 staff.'])}${job('Senior Operations Manager', 'Delta Logistics, Chennai', '2014 – 2019', ['Launched a regional hub that grew revenue by 35% in two years.'])}
${h('Education')}<div><b>MBA – Operations</b>, PSG Institute of Management · 2014<br><b>B.E. Mechanical Engineering</b>, NIT Trichy · 2011</div>
${h('Board & Affiliations')}<div>Member, Confederation of Indian Industry (CII) – Coimbatore chapter.</div>`),
  },
  {
    id: 'cover-letter', category: 'Letters', name: 'Cover Letter', accent: '#1f3a5f', font: 'Calibri',
    description: 'Professional job application letter with a strong opening and clear call to action.',
    build: (c) => pad(`<div style="font-size:22px;font-weight:700;color:${AC}">${c.name}</div><div style="font-size:12px;margin-bottom:24px">${c.email} · +91 98765 43210 · Coimbatore, Tamil Nadu</div><div>${c.date}</div><div style="margin:14px 0">Hiring Manager<br>Acme Technologies<br>Bengaluru, Karnataka</div><div><b>Subject: Application for Software Developer</b></div><p>Dear Hiring Manager,</p><p>I am excited to apply for the Software Developer position at Acme Technologies. With three years of experience building web applications in React and Python, I have delivered products that serve thousands of users and consistently improved performance and reliability.</p><p>At JM Vertex Technologies I led the development of a document workspace that reduced manual processing time by 40%. I enjoy turning ambiguous problems into clear, maintainable solutions and working closely with designers and product teams.</p><p>I would welcome the chance to discuss how my skills can support Acme&apos;s goals. Thank you for your time and consideration.</p><p>Sincerely,</p>${sig(c.name)}`),
  },
  {
    id: 'resignation', category: 'Letters', name: 'Resignation Letter', accent: '#374151', font: 'Calibri',
    description: 'Polite, professional resignation with notice period and handover offer.',
    build: (c) => pad(`${c.date}<div style="margin:14px 0">To,<br>The Manager – Human Resources<br>Your Company Name Pvt. Ltd.<br>Coimbatore</div><p><b>Subject: Resignation from the position of Software Developer</b></p><p>Dear Sir/Madam,</p><p>I am writing to formally resign from my position as Software Developer, effective after completion of my 30-day notice period, with my last working day being <b>[last working date]</b>.</p><p>I am grateful for the opportunities and support I received during my time here. I will ensure a smooth handover of my responsibilities and am happy to assist in training my replacement.</p><p>Thank you for your guidance and understanding.</p><p>Yours sincerely,</p>${sig(c.name, 'Employee ID: ____')}`),
  },
  {
    id: 'leave-application', category: 'Letters', name: 'Leave Application', accent: '#0f766e', font: 'Calibri',
    description: 'Simple leave request for office or school with dates and reason.',
    build: (c) => pad(`${c.date}<div style="margin:14px 0">To,<br>The Reporting Manager<br>Your Company Name Pvt. Ltd.</div><p><b>Subject: Application for leave</b></p><p>Respected Sir/Madam,</p><p>I kindly request you to grant me leave from <b>[start date]</b> to <b>[end date]</b> (total <b>[number]</b> days) due to <b>[reason – e.g. a family function / medical reason]</b>.</p><p>I will complete my pending work before leaving and can be reached by phone in case of any urgent matter.</p><p>Thank you for your consideration.</p><p>Yours faithfully,</p>${sig(c.name)}`),
  },
  {
    id: 'recommendation', category: 'Letters', name: 'Recommendation Letter', accent: '#4f46e5', font: 'Georgia',
    description: 'Reference letter for a student or employee, ready to personalise.',
    build: (c) => pad(letterHead(c) + `<div>${c.date}</div><p><b>To Whom It May Concern,</b></p><p>I am pleased to recommend <b>[Candidate Name]</b>, who worked with me as <b>[role]</b> for <b>[duration]</b>. During this time, they consistently showed strong technical skills, reliability and a positive attitude.</p><p>They completed every assignment on time, took initiative on difficult problems and worked well with the whole team. I am confident they will be a valuable addition to any organisation or programme.</p><p>Please feel free to contact me if you need more information.</p><p>Sincerely,</p>${sig('[Your Name]', '[Designation]')}`),
  },
  {
    id: 'authorization', category: 'Letters', name: 'Authorization Letter', accent: '#374151', font: 'Calibri',
    description: 'Authorise someone to act or collect documents on your behalf.',
    build: (c) => pad(`${c.date}<div style="margin:14px 0">To,<br>The Concerned Authority<br>[Office / Organisation name]</div><p><b>Subject: Authorization letter</b></p><p>I, <b>${c.name}</b>, hereby authorise <b>[Representative name]</b> (ID proof: <b>[ID type and number]</b>) to <b>[collect documents / sign on my behalf / attend the meeting]</b> on my behalf on <b>[date]</b>.</p><p>Their signature is given below for verification. Kindly extend your cooperation.</p><p>Thank you.</p><div style="display:flex;justify-content:space-between;margin-top:40px"><div style="border-top:1px solid #333;width:190px;padding-top:4px">Signature of ${c.name}</div><div style="border-top:1px solid #333;width:190px;padding-top:4px">Signature of Representative</div></div>`),
  },
  {
    id: 'offer-letter', category: 'Business', name: 'Offer Letter', accent: '#6a3df0', font: 'Calibri',
    description: 'Job offer with role, salary, joining date and terms.',
    build: (c) => pad(letterHead(c) + `<div>${c.date}</div><p>Dear <b>[Candidate Name]</b>,</p><p>We are delighted to offer you the position of <b>Software Developer</b> at Your Company Name Pvt. Ltd. Your date of joining will be <b>[joining date]</b>.</p><table style="border-collapse:collapse;width:100%;margin:10px 0"><tr><td style="border:1px solid #bbb;padding:7px 10px"><b>Annual CTC</b></td><td style="border:1px solid #bbb;padding:7px 10px">₹ 6,00,000</td></tr><tr><td style="border:1px solid #bbb;padding:7px 10px"><b>Work location</b></td><td style="border:1px solid #bbb;padding:7px 10px">Coimbatore</td></tr><tr><td style="border:1px solid #bbb;padding:7px 10px"><b>Probation</b></td><td style="border:1px solid #bbb;padding:7px 10px">6 months</td></tr></table><p>Please sign and return a copy of this letter as your acceptance by <b>[date]</b>. We look forward to welcoming you to the team.</p>${sig('HR Manager', 'Your Company Name Pvt. Ltd.')}<div style="margin-top:28px;font-size:12px">I accept the above offer. Signature: ____________  Date: ________</div>`),
  },
  {
    id: 'experience-certificate', category: 'Certificates', name: 'Experience Certificate', accent: '#1f3a5f', font: 'Georgia',
    description: 'Formal experience / service certificate on letterhead.',
    build: (c) => pad(letterHead(c) + `<div style="text-align:center;font-size:22px;font-weight:700;text-decoration:underline;margin-bottom:20px">EXPERIENCE CERTIFICATE</div><div style="text-align:right">Date: ${c.date}</div><p style="line-height:2;text-align:justify;margin-top:20px">This is to certify that <b>${c.name}</b> was employed with <b>Your Company Name Pvt. Ltd.</b> as <b>Software Developer</b> from <b>[start date]</b> to <b>[end date]</b>.</p><p style="line-height:2;text-align:justify">During this period, their conduct and performance were found to be satisfactory. We wish them every success in future endeavours.</p>${sig('Authorised Signatory', 'HR Manager')}`),
  },
  {
    id: 'no-due', category: 'Certificates', name: 'No Due Certificate', accent: '#0f766e', font: 'Georgia',
    description: 'No-dues clearance for employees, students or vendors, with department sign-offs.',
    build: (c) => pad(letterHead(c) + `<div style="text-align:center;font-size:22px;font-weight:700;text-decoration:underline;margin-bottom:20px">NO DUE CERTIFICATE</div><div style="text-align:right">Date: ${c.date}</div><p style="line-height:2;text-align:justify;margin-top:18px">This is to certify that <b>${c.name}</b> (ID / Reg. No.: <b>[ID number]</b>) has cleared all dues and returned all property of the organisation. There are no outstanding payments, library books, equipment or documents pending against them as on the date above.</p><table style="border-collapse:collapse;width:100%;margin-top:14px"><tr style="background:${AC};color:#fff"><td style="border:1px solid #999;padding:7px 10px">Department</td><td style="border:1px solid #999;padding:7px 10px">Status</td><td style="border:1px solid #999;padding:7px 10px">Sign &amp; Date</td></tr>${['Accounts / Fees', 'Library', 'IT / Equipment', 'Administration', 'Department Head'].map((d) => `<tr><td style="border:1px solid #999;padding:9px 10px">${d}</td><td style="border:1px solid #999;padding:9px 10px">Cleared</td><td style="border:1px solid #999;padding:9px 10px">&nbsp;</td></tr>`).join('')}</table>${sig('Authorised Signatory')}`),
  },
  {
    id: 'noc', category: 'Certificates', name: 'No Objection Certificate (NOC)', accent: '#374151', font: 'Georgia',
    description: 'NOC for employment, higher studies, travel or tenancy.',
    build: (c) => pad(letterHead(c) + `<div style="text-align:center;font-size:22px;font-weight:700;text-decoration:underline;margin-bottom:20px">NO OBJECTION CERTIFICATE</div><div style="text-align:right">Date: ${c.date}</div><p style="line-height:2;text-align:justify;margin-top:18px">This is to certify that <b>Your Company Name Pvt. Ltd.</b> has <b>no objection</b> to <b>${c.name}</b> <b>[purpose – e.g. pursuing higher studies / applying for a visa / taking up external work]</b>.</p><p style="line-height:2;text-align:justify">This certificate is issued on request for the purpose stated above and carries no financial liability for the organisation.</p>${sig('Authorised Signatory', 'HR Manager')}`),
  },
  {
    id: 'bonafide', category: 'Certificates', name: 'Bonafide Certificate', accent: '#4f46e5', font: 'Georgia',
    description: 'Student bonafide certificate for bank, passport or scholarship use.',
    build: (c) => pad(`<div style="text-align:center"><div style="font-size:24px;font-weight:700;color:${AC}">Your College / School Name</div><div style="font-size:12px">Address line, City, State – PIN · Phone · Email</div></div><div style="border-bottom:3px solid ${AC};margin:10px 0 24px"></div><div style="text-align:center;font-size:22px;font-weight:700;text-decoration:underline;margin-bottom:20px">BONAFIDE CERTIFICATE</div><p style="line-height:2;text-align:justify">This is to certify that <b>${c.name}</b>, son/daughter of <b>[Parent name]</b>, is a bonafide student of this institution, studying in <b>[Course / Class]</b> during the academic year <b>2025 – 2026</b> (Register No.: <b>[number]</b>).</p><p style="line-height:2;text-align:justify">Their conduct and character are good. This certificate is issued on request for <b>[purpose]</b>.</p><div style="display:flex;justify-content:space-between;margin-top:70px"><div>Date: ${c.date}<br>Place: Coimbatore</div><div style="text-align:center"><div style="border-top:1px solid #333;width:190px;padding-top:4px"><b>Principal</b></div></div></div>`),
  },
  {
    id: 'internship-certificate', category: 'Certificates', name: 'Internship Completion Certificate', accent: '#6a3df0', font: 'Georgia',
    description: 'Certificate of internship completion with a decorative border.',
    build: (c) => cert('Certificate of Internship', `<div style="text-align:center">This is to certify that</div><div style="text-align:center;font-size:30px;font-weight:700;color:${AC};font-family:Georgia,serif;margin:6px 0">${c.name}</div><div style="text-align:center">has successfully completed an internship as <b>Web Development Intern</b> from <b>[start date]</b> to <b>[end date]</b> and demonstrated excellent dedication, learning ability and professionalism. We wish them success in their future career.</div>`, c),
  },
  {
    id: 'achievement-certificate', category: 'Certificates', name: 'Certificate of Achievement', accent: '#b45309', font: 'Georgia',
    description: 'Award or appreciation certificate for competitions, events and top performers.',
    build: (c) => cert('Certificate of Achievement', `<div style="text-align:center">This certificate is proudly presented to</div><div style="text-align:center;font-size:32px;font-weight:700;color:${AC};font-family:Georgia,serif;margin:6px 0">${c.name}</div><div style="text-align:center">in recognition of outstanding performance and achievement as <b>First Place</b> in the <b>[event name]</b> held on <b>[date]</b>. Congratulations and keep shining!</div>`, c),
  },
  {
    id: 'relieving', category: 'Certificates', name: 'Relieving Letter', accent: '#1f3a5f', font: 'Calibri',
    description: 'Confirms the employee has been relieved of duties after resignation.',
    build: (c) => pad(letterHead(c) + `<div>${c.date}</div><p><b>Subject: Relieving letter</b></p><p>Dear <b>${c.name}</b>,</p><p>This is with reference to your resignation dated <b>[resignation date]</b>. We confirm that you are relieved from your duties as <b>Software Developer</b> with effect from the close of working hours on <b>[last working date]</b>.</p><p>You have handed over all company assets and completed the exit formalities. We thank you for your contribution and wish you success in your future.</p>${sig('HR Manager', 'Your Company Name Pvt. Ltd.')}`),
  },
  {
    id: 'invoice', category: 'Business', name: 'Invoice', accent: '#2563eb', font: 'Calibri',
    description: 'GST-style invoice with itemised table, tax and totals.',
    build: (c) => pad(`<div style="display:flex;justify-content:space-between"><div><div style="font-size:30px;font-weight:700;color:${AC}">INVOICE</div><div style="font-size:12px">Invoice No: INV-0001<br>Date: ${c.date}<br>Due: [due date]</div></div><div style="text-align:right"><b>Your Company Name</b><br>12, Business Park Road<br>Coimbatore – 641001<br>GSTIN: [GST number]</div></div><div style="margin:22px 0"><b>Bill to</b><br>[Client name]<br>[Client address]</div><table style="border-collapse:collapse;width:100%"><tr style="background:${AC};color:#fff"><td style="padding:8px">#</td><td style="padding:8px">Description</td><td style="padding:8px;text-align:right">Qty</td><td style="padding:8px;text-align:right">Rate (₹)</td><td style="padding:8px;text-align:right">Amount (₹)</td></tr>${[['Website design', 1, 25000], ['Hosting (1 year)', 1, 6000], ['Maintenance (3 months)', 3, 2000]].map((r, i) => `<tr><td style="padding:8px;border-bottom:1px solid #ddd">${i + 1}</td><td style="padding:8px;border-bottom:1px solid #ddd">${r[0]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${r[1]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${r[2]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${Number(r[1]) * Number(r[2])}</td></tr>`).join('')}</table><div style="text-align:right;margin-top:12px;line-height:1.9">Subtotal: ₹37,000<br>GST (18%): ₹6,660<br><b style="font-size:18px;color:${AC}">Total: ₹43,660</b></div><div style="margin-top:26px;font-size:12px"><b>Payment details</b><br>Bank: [Bank name] · A/C: [account number] · IFSC: [IFSC]<br>Thank you for your business!</div>`),
  },
  {
    id: 'quotation', category: 'Business', name: 'Quotation', accent: '#0f766e', font: 'Calibri',
    description: 'Price quotation with validity and terms.',
    build: (c) => pad(`<div style="font-size:30px;font-weight:700;color:${AC}">QUOTATION</div><div style="font-size:12px;margin-bottom:18px">Quote No: Q-0001 · Date: ${c.date} · Valid for 15 days</div><div><b>Prepared for:</b> [Client name]<br><b>Prepared by:</b> Your Company Name</div><table style="border-collapse:collapse;width:100%;margin:16px 0"><tr style="background:${AC};color:#fff"><td style="padding:8px">Item</td><td style="padding:8px;text-align:right">Qty</td><td style="padding:8px;text-align:right">Unit price (₹)</td><td style="padding:8px;text-align:right">Total (₹)</td></tr>${[['Item / service 1', 2, 5000], ['Item / service 2', 1, 12000]].map((r) => `<tr><td style="padding:8px;border-bottom:1px solid #ddd">${r[0]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${r[1]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${r[2]}</td><td style="padding:8px;border-bottom:1px solid #ddd;text-align:right">${Number(r[1]) * Number(r[2])}</td></tr>`).join('')}</table><div style="text-align:right"><b style="font-size:18px;color:${AC}">Grand total: ₹22,000 + GST</b></div><div style="margin-top:22px"><b>Terms</b>${li(['50% advance, balance on delivery.', 'Prices are exclusive of GST.', 'Delivery within 7 working days of the advance.'])}</div>${sig(c.name)}`),
  },
  {
    id: 'receipt', category: 'Business', name: 'Payment Receipt', accent: '#374151', font: 'Calibri',
    description: 'Simple receipt acknowledging a payment.',
    build: (c) => pad(`<div style="border:2px solid ${AC};padding:28px"><div style="display:flex;justify-content:space-between"><div style="font-size:26px;font-weight:700;color:${AC}">PAYMENT RECEIPT</div><div>No: R-0001<br>Date: ${c.date}</div></div><p style="line-height:2;margin-top:22px">Received with thanks from <b>[Payer name]</b> the sum of <b>₹ [amount]</b> (Rupees <b>[amount in words]</b> only) towards <b>[purpose]</b> by <b>[cash / UPI / bank transfer]</b>.</p><div style="display:flex;justify-content:space-between;margin-top:50px"><div>Amount: <b style="font-size:20px">₹ [amount]</b></div><div style="border-top:1px solid #333;width:190px;padding-top:4px;text-align:center">Received by<br><b>${c.name}</b></div></div></div>`),
  },
  {
    id: 'business-proposal', category: 'Business', name: 'Business Proposal', accent: '#6a3df0', font: 'Calibri',
    description: 'Structured proposal with problem, solution, timeline and pricing.',
    build: (c) => `<div style="background:${AC};color:#fff;padding:60px 56px"><div style="font-size:14px;letter-spacing:.2em">PROPOSAL</div><div style="font-size:36px;font-weight:700;margin:8px 0">Website Redesign &amp; SEO Growth</div><div>Prepared for [Client name] · by ${c.name} · ${c.date}</div></div>${pad(`${h('1. Overview')}<div>We propose a modern, fast and search-optimised website that turns visitors into customers.</div>${h('2. The problem')}${li(['Slow pages and a dated design hurt trust.', 'Low search visibility; most traffic is paid.'])}${h('3. Our solution')}${li(['Redesign with a mobile-first, accessible layout.', 'Technical SEO and content plan for 20 target keywords.', 'Analytics dashboard to track leads weekly.'])}${h('4. Timeline')}${li(['Week 1–2: Discovery and design', 'Week 3–5: Development', 'Week 6: Testing and launch'])}${h('5. Investment')}<div style="font-size:20px"><b>₹ 1,25,000</b> <span style="font-size:12px">(50% to start, 50% on launch)</span></div>${h('6. Next steps')}<div>Approve this proposal and we will schedule a kick-off call within 2 working days.</div>`, '10px 56px 40px')}`,
  },
  {
    id: 'meeting-minutes', category: 'Business', name: 'Meeting Minutes', accent: '#0f766e', font: 'Calibri',
    description: 'Agenda, attendees, decisions and action items with owners.',
    build: (c) => pad(`<div style="font-size:28px;font-weight:700;color:${AC}">Meeting Minutes</div><div style="font-size:12px;margin-bottom:12px">Date: ${c.date} · Time: 10:00 AM · Venue: Conference Room 2 · Minutes by: ${c.name}</div>${h('Attendees')}<div>[Name 1], [Name 2], [Name 3]</div>${h('Agenda')}${li(['Project status update', 'Budget review', 'Next sprint planning'])}${h('Discussion & decisions')}${li(['Project is on track; launch date remains [date].', 'Budget increase of 10% approved for testing.'])}${h('Action items')}<table style="border-collapse:collapse;width:100%"><tr style="background:${AC};color:#fff"><td style="padding:7px">Action</td><td style="padding:7px">Owner</td><td style="padding:7px">Due</td></tr><tr><td style="padding:7px;border:1px solid #ccc">Share revised plan</td><td style="padding:7px;border:1px solid #ccc">[Name]</td><td style="padding:7px;border:1px solid #ccc">[date]</td></tr><tr><td style="padding:7px;border:1px solid #ccc">Update budget sheet</td><td style="padding:7px;border:1px solid #ccc">[Name]</td><td style="padding:7px;border:1px solid #ccc">[date]</td></tr></table>${h('Next meeting')}<div>[Date and time]</div>`),
  },
  {
    id: 'project-cover', category: 'Education & Events', name: 'Project Report Cover Page', accent: '#4f46e5', font: 'Georgia',
    description: 'Title page for college project reports and records.',
    build: (c) => pad(`<div style="border:3px double ${AC};padding:50px 40px;text-align:center;min-height:980px"><div style="font-size:18px;font-weight:700;letter-spacing:.1em">YOUR COLLEGE NAME</div><div style="font-size:12px">(Affiliated to Anna University, Chennai)</div><div style="margin:70px 0 20px;font-size:14px">A PROJECT REPORT ON</div><div style="font-size:30px;font-weight:700;color:${AC};line-height:1.3">&ldquo;Smart Document Management System&rdquo;</div><div style="margin:50px 0 10px">Submitted by</div><div style="font-size:20px;font-weight:700">${c.name}</div><div>Register No.: [number]</div><div style="margin:40px 0 10px">in partial fulfilment for the award of the degree of</div><div style="font-size:18px;font-weight:700">BACHELOR OF ENGINEERING</div><div>in Computer Science and Engineering</div><div style="margin-top:50px">Under the guidance of<br><b>[Guide name]</b>, Assistant Professor</div><div style="margin-top:60px;font-size:14px">Department of Computer Science and Engineering<br>Academic Year 2025 – 2026</div></div>`),
  },
  {
    id: 'invitation', category: 'Education & Events', name: 'Event Invitation', accent: '#db2777', font: 'Georgia',
    description: 'Elegant invitation for a party, launch or ceremony.',
    build: (c) => `<div style="background:linear-gradient(160deg,${AC},#7c3aed);color:#fff;text-align:center;padding:90px 50px;min-height:1000px"><div style="letter-spacing:.35em;font-size:14px">YOU ARE INVITED</div><div style="font-size:48px;font-weight:700;margin:26px 0;font-family:Georgia,serif;line-height:1.15">Annual Day<br>Celebration</div><div style="width:100px;height:3px;background:#fff;margin:0 auto 30px;opacity:.8"></div><div style="font-size:18px;line-height:2">Saturday, [date]<br>6:00 PM onwards<br>Grand Hall, [Venue name], Coimbatore</div><div style="margin:36px auto;max-width:420px;font-size:15px;line-height:1.8;opacity:.95">Join us for an evening of music, awards and dinner. We would be delighted to have you with us.</div><div style="font-size:14px">RSVP: ${c.name} · ${c.email}</div></div>`,
  },
];

export const templateCategories: ('All' | TemplateCategory)[] = ['All', 'Resume & CV', 'Letters', 'Certificates', 'Business', 'Education & Events'];

export function buildDefaultHtml(item: TemplateItem, name: string, email: string) {
  const date = new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  return item.build({ name: name || 'Your Name', email: email || 'you@example.com', date });
}

// ---------------------------------------------------------------- ATS check (runs in the browser)
export type AtsCheck = { label: string; ok: boolean; tip: string; points: number };
export type AtsResult = { score: number; checks: AtsCheck[]; matched: string[]; missing: string[] };

const STOP = new Set('a an and are as at be by for from has have in is it of on or that the to was were will with you your our we they this their can able must should work experience team role about who what when where which'.split(' '));
const ACTION_VERBS = ['built', 'led', 'developed', 'designed', 'improved', 'reduced', 'increased', 'launched', 'managed', 'created', 'delivered', 'optimised', 'optimized', 'implemented', 'automated', 'achieved', 'scaled', 'organised', 'organized', 'coordinated', 'analysed', 'analyzed', 'won'];

export function atsScore(text: string, jobDescription = ''): AtsResult {
  const lower = text.toLowerCase();
  const words = lower.split(/\s+/).filter(Boolean).length;
  const has = (re: RegExp) => re.test(lower);
  const checks: AtsCheck[] = [
    { label: 'Contact details', ok: /[\w.+-]+@[\w-]+\.[\w.]+/.test(text) && /\+?\d[\d\s-]{8,}/.test(text), tip: 'Include a professional email and a phone number at the top.', points: 12 },
    { label: 'Experience / Projects section', ok: has(/experience|internship|projects?/), tip: 'Add a section titled “Experience” or “Projects”.', points: 14 },
    { label: 'Education section', ok: has(/education|b\.?e\.?|b\.?tech|degree|university|college/), tip: 'Add an “Education” section with your degree and year.', points: 12 },
    { label: 'Skills section', ok: has(/skills|technologies|tools/), tip: 'List your skills under a “Skills” heading so the parser can read them.', points: 12 },
    { label: 'Summary / objective', ok: has(/summary|objective|profile|about me/), tip: 'Add a 2–3 line professional summary.', points: 8 },
    { label: 'Measurable results (numbers, %)', ok: (text.match(/\d+\s?(%|\+|k\b|crore|lakh|users|ms)/gi) ?? []).length >= 3, tip: 'Add at least 3 quantified achievements, e.g. “reduced load time by 40%”.', points: 14 },
    { label: 'Action verbs', ok: ACTION_VERBS.filter((v) => lower.includes(v)).length >= 4, tip: 'Start bullets with verbs such as built, led, improved, delivered.', points: 8 },
    { label: 'Length (250–900 words)', ok: words >= 250 && words <= 900, tip: words < 250 ? 'Too short – add detail about your work.' : 'Too long – aim for one or two pages.', points: 10 },
  ];
  let earned = checks.filter((c) => c.ok).reduce((n, c) => n + c.points, 0);
  let total = checks.reduce((n, c) => n + c.points, 0);
  let matched: string[] = [];
  let missing: string[] = [];
  if (jobDescription.trim()) {
    const freq = new Map<string, number>();
    jobDescription.toLowerCase().match(/[a-z][a-z+#.]{2,}/g)?.forEach((w) => { if (!STOP.has(w)) freq.set(w, (freq.get(w) ?? 0) + 1); });
    const keywords = [...freq.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20).map(([w]) => w);
    matched = keywords.filter((k) => lower.includes(k));
    missing = keywords.filter((k) => !lower.includes(k));
    const share = keywords.length ? matched.length / keywords.length : 1;
    checks.push({ label: `Job-description keywords (${matched.length}/${keywords.length})`, ok: share >= 0.6, tip: `Work these in where true: ${missing.slice(0, 6).join(', ') || '—'}.`, points: 25 });
    earned += Math.round(25 * share);
    total += 25;
  }
  return { score: Math.round((earned / total) * 100), checks, matched, missing };
}
