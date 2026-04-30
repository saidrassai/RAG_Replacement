# arXiv Search Results: Financial LLM Fine-Tuning Papers

Generated: 2026-04-30 16:08

---

## Query 1: Finance + Qwen + Fine-Tuning

**Query:** `all:(finance AND qwen AND fine-tuning)`  |  **Results:** 12

### 1. FinTrace: Holistic Trajectory-Level Evaluation of LLM Tool Calling for Long-Horizon Financial Tasks

- **arXiv ID:** `2604.10015v2`
- **Date:** 2026-04-11
- **Authors:** Yupeng Cao, Haohang Li, Weijin Liu, Wenbo Cao, Anke Xu et al.
- **Categories:** cs.AI, cs.CE, cs.CL, cs.MM
- **Summary:** Recent studies demonstrate that tool-calling capability enables large language models (LLMs) to interact with external environments for long-horizon financial tasks. While existing benchmarks have begun evaluating financial tool calling, they focus on limited scenarios and rely on call-level metrics that fail to capture trajectory-level reasoning quality. To address this gap, we introduce FinTrace, a benchmark comprising 800 expert-annotated trajectories spanning 34 real-world financial task categories across multiple difficulty levels.

### 2. You only need 4 extra tokens: Synergistic Test-time Adaptation for LLMs

- **arXiv ID:** `2510.10223v2`
- **Date:** 2025-10-11
- **Authors:** Yijie Xu, Huizai Yao, Zhiyu Guo, Pengteng Li, Aiwei Liu et al.
- **Categories:** cs.CL, cs.AI, cs.LG
- **Summary:** Large language models (LLMs) are increasingly deployed in specialized domains such as finance, medicine, and agriculture, where they face significant distribution shifts from their training data. Domain-specific fine-tuning can mitigate this challenge but relies on high-quality labeled data that is expensive and slow to collect in expertise-limited settings. We study label-free test-time adaptation for language models and present SyTTA, an inference-time framework that adapts models on-the-fly without additional supervision.

### 3. Synthesizing Behaviorally-Grounded Reasoning Chains: A Data-Generation Framework for Personal Finance LLMs

- **arXiv ID:** `2509.14180v1`
- **Date:** 2025-09-17
- **Authors:** Akhil Theerthala
- **Categories:** cs.CL, cs.AI, cs.LG
- **Summary:** Personalized financial advice requires consideration of user goals, constraints, risk tolerance, and jurisdiction. Prior LLM work has focused on support systems for investors and financial planners. Simultaneously, numerous recent studies examine broader personal finance tasks, including budgeting, debt management, retirement, and estate planning, through agentic pipelines that incur high maintenance costs, yielding less than 25% of their expected financial returns.

### 4. TULIP: Adapting Open-Source Large Language Models for Underrepresented Languages and Specialized Financial Tasks

- **arXiv ID:** `2508.16243v1`
- **Date:** 2025-08-22
- **Authors:** İrem Demirtaş, Burak Payzun, Seçil Arslan
- **Categories:** cs.CL
- **Summary:** Thanks to the growing popularity of large language models over the years, there is great potential for their applications in finance. Despite the exceptional performance of larger proprietary models, which are presented as black-box solutions through APIs, smaller models that can be hosted on-premise present opportunities for adaptability and privacy. Especially in cases where the management of sensitive information and application of domain knowledge is important, like finance, enhancing the capabilities of smaller models becomes crucial, notably for underrepresented languages.

### 5. Fin-PRM: A Domain-Specialized Process Reward Model for Financial Reasoning in Large Language Models

- **arXiv ID:** `2508.15202v1`
- **Date:** 2025-08-21
- **Authors:** Yuanchen Zhou, Shuo Jiang, Jie Zhu, Junhui Li, Lifan Guo et al.
- **Categories:** cs.CL
- **Summary:** Process Reward Models (PRMs) have emerged as a promising framework for supervising intermediate reasoning in large language models (LLMs), yet existing PRMs are primarily trained on general or Science, Technology, Engineering, and Mathematics (STEM) domains and fall short in domain-specific contexts such as finance, where reasoning is more structured, symbolic, and sensitive to factual and regulatory correctness. We introduce \textbf{Fin-PRM}, a domain-specialized, trajectory-aware PRM tailored to evaluate intermediate reasoning steps in financial tasks. Fin-PRM integrates step-level and tr...

### 6. Datarus-R1: An Adaptive Multi-Step Reasoning LLM for Automated Data Analysis

- **arXiv ID:** `2508.13382v1`
- **Date:** 2025-08-18
- **Authors:** Ayoub Ben Chaliah, Hela Dellagi
- **Categories:** cs.CL, cs.AI
- **Summary:** We present Datarus-R1-14B, a 14 B-parameter open-weights language model fine-tuned from Qwen 2.5-14B-Instruct to act as a virtual data analyst and graduate-level problem solver. Datarus is trained not on isolated question-answer pairs but on full analytical trajectories including reasoning steps, code execution, error traces, self-corrections, and final conclusions, all captured in a ReAct-style notebook format spanning finance, medicine, numerical analysis, and other quantitative domains. Our training pipeline combines (i) a trajectory-centric synthetic data generator that yielded 144 000 ...

### 7. Technical Report: Full-Stack Fine-Tuning for the Q Programming Language

- **arXiv ID:** `2508.06813v2`
- **Date:** 2025-08-09
- **Authors:** Brendan R. Hogan, Will Brown, Adel Boyarsky, Anderson Schneider, Yuriy Nevmyvaka
- **Categories:** cs.LG, cs.PL
- **Summary:** Even though large language models are becoming increasingly capable, it is still unreasonable to expect them to excel at tasks that are under-represented on the Internet. Leveraging LLMs for specialized applications, particularly in niche programming languages and private domains, remains challenging and largely unsolved. In this work, we address this gap by presenting a comprehensive, open-source approach for adapting LLMs to the Q programming language, a popular tool in quantitative finance that is much less present on the Internet compared to Python, C, Java, and other ``mainstream" lang...

### 8. Synthetic Data RL: Task Definition Is All You Need

- **arXiv ID:** `2505.17063v1`
- **Date:** 2025-05-18
- **Authors:** Yiduo Guo, Zhen Guo, Chuanwei Huang, Zi-Ang Wang, Zekai Zhang et al.
- **Categories:** cs.CL, cs.AI, cs.LG
- **Summary:** Reinforcement learning (RL) is a powerful way to adapt foundation models to specialized tasks, but its reliance on large-scale human-labeled data limits broad adoption. We introduce Synthetic Data RL, a simple and general framework that reinforcement fine-tunes models using only synthetic data generated from a task definition. Our method first generates question and answer pairs from the task definition and retrieved documents, then adapts the difficulty of the question based on model solvability, and selects questions using the average pass rate of the model across samples for RL training.

### 9. Fusing Bidirectional Chains of Thought and Reward Mechanisms A Method for Enhancing Question-Answering Capabilities of Large Language Models for Chinese Intangible Cultural Heritage

- **arXiv ID:** `2505.08167v4`
- **Date:** 2025-05-13
- **Authors:** Ruilin Liu, Zhixiao Zhao, Jieqiong Li, Chang Liu, Dongbo Wang
- **Categories:** cs.CL, cs.AI
- **Summary:** The rapid development of large language models (LLMs) has provided significant support and opportunities for the advancement of domain-specific LLMs. However, fine-tuning these large models using Intangible Cultural Heritage (ICH) data inevitably faces challenges such as bias, incorrect knowledge inheritance, and catastrophic forgetting. To address these issues, we propose a novel training method that integrates a bidirectional chains of thought and a reward mechanism.

### 10. The Power of Small LLMs in Geometry Generation for Physical Simulations

- **arXiv ID:** `2503.18178v1`
- **Date:** 2025-03-23
- **Authors:** Ossama Shafiq, Bahman Ghiassi, Alessio Alexiadis
- **Categories:** cs.CE
- **Summary:** Engineers widely rely on simulation platforms like COMSOL or ANSYS to model and optimise processes. However, setting up such simulations requires expertise in defining geometry, generating meshes, establishing boundary conditions, and configuring solvers. This research aims to simplify this process by enabling engineers to describe their setup in plain language, allowing a Large Language Model (LLM) to generate the necessary input files for their specific application.

### 11. VersaTune: An Efficient Data Composition Framework for Training Multi-Capability LLMs

- **arXiv ID:** `2411.11266v5`
- **Date:** 2024-11-18
- **Authors:** Keer Lu, Keshi Zhao, Zhuoran Zhang, Zheng Liang, Da Pan et al.
- **Categories:** cs.CL
- **Summary:** As demonstrated by the proprietary Large Language Models (LLMs) such as GPT and Claude series, LLMs have the potential to achieve remarkable proficiency across a wide range of domains, including law, medicine, finance, science, code, etc., all within a single model. These capabilities are further augmented during the Supervised Fine-Tuning (SFT) phase. Despite their potential, existing work mainly focuses on domain-specific enhancements during fine-tuning, the challenge of which lies in catastrophic forgetting of knowledge across other domains.

### 12. FAMMA: A Benchmark for Financial Domain Multilingual Multimodal Question Answering

- **arXiv ID:** `2410.04526v4`
- **Date:** 2024-10-06
- **Authors:** Siqiao Xue, Xiaojing Li, Fan Zhou, Qingyang Dai, Zhixuan Chu et al.
- **Categories:** cs.CL, cs.AI
- **Summary:** In this paper, we introduce FAMMA, an open-source benchmark for \underline{f}in\underline{a}ncial \underline{m}ultilingual \underline{m}ultimodal question \underline{a}nswering (QA). Our benchmark aims to evaluate the abilities of large language models (LLMs) in answering complex reasoning questions that require advanced financial knowledge. The benchmark has two versions: FAMMA-Basic consists of 1,945 questions extracted from university textbooks and exams, along with human-annotated answers and rationales; FAMMA-LivePro consists of 103 novel questions created by human domain experts, with...

---

## Query 2: Financial LLM SFT / RLHF / GRPO / DPO

**Query:** `all:(financial AND LLM AND (SFT OR RLHF OR GRPO OR DPO))`  |  **Results:** 15

### 1. Hindsight Preference Optimization for Financial Time Series Advisory

- **arXiv ID:** `2604.23988v1`
- **Date:** 2026-04-27
- **Authors:** Yanwei Cui, Guanghui Wang, Xing Zhang, Peiyang He, Ziyuan Li et al.
- **Categories:** cs.LG, cs.AI
- **Summary:** Time series models predict numbers; decision-makers need advisory -- directional signals with reasoning, actionable suggestions, and risk management. Training language models for such predictive advisory faces a fundamental challenge: quality depends on outcomes unknown at prediction time. We bridge two ideas from reinforcement learning -- using information unavailable during execution to retrospectively generate training signal, and preference alignment -- and propose Hindsight Preference Optimization: observed outcomes let an LLM judge rank candidate advisories on dimensions that scalar m...

### 2. Reducing Detail Hallucinations in Long-Context Regulatory Understanding via Targeted Preference Optimization

- **arXiv ID:** `2604.23113v1`
- **Date:** 2026-04-25
- **Authors:** Yang Liu, Bin Chong, Yuhan Lin, Chongyang Zhang, Hao Zheng et al.
- **Categories:** cs.SI
- **Summary:** Large language models (LLMs) frequently produce \emph{detail hallucinations} when processing long regulatory documents, including subtle errors in threshold values, units, scopes, obligation levels, and conditions that preserve surface plausibility while corrupting safety-critical parameters. We formalize this phenomenon through a fine-grained \emph{Detail Error Taxonomy} of five error types and introduce \textbf{DetailBench}, a benchmark built from 172 real regulatory documents and 150 synthetic documents spanning three jurisdictions, with human-annotated detail-level ground truth comprisi...

### 3. OOM-RL: Out-of-Money Reinforcement Learning Market-Driven Alignment for LLM-Based Multi-Agent Systems

- **arXiv ID:** `2604.11477v1`
- **Date:** 2026-04-13
- **Authors:** Kun Liu, Liqun Chen
- **Categories:** cs.AI, cs.SE, q-fin.TR
- **Summary:** The alignment of Multi-Agent Systems (MAS) for autonomous software engineering is constrained by evaluator epistemic uncertainty. Current paradigms, such as Reinforcement Learning from Human Feedback (RLHF) and AI Feedback (RLAIF), frequently induce model sycophancy, while execution-based environments suffer from adversarial "Test Evasion" by unconstrained agents. In this paper, we introduce an objective alignment paradigm: \textbf{Out-of-Money Reinforcement Learning (OOM-RL)}.

### 4. FinTrace: Holistic Trajectory-Level Evaluation of LLM Tool Calling for Long-Horizon Financial Tasks

- **arXiv ID:** `2604.10015v2`
- **Date:** 2026-04-11
- **Authors:** Yupeng Cao, Haohang Li, Weijin Liu, Wenbo Cao, Anke Xu et al.
- **Categories:** cs.AI, cs.CE, cs.CL, cs.MM
- **Summary:** Recent studies demonstrate that tool-calling capability enables large language models (LLMs) to interact with external environments for long-horizon financial tasks. While existing benchmarks have begun evaluating financial tool calling, they focus on limited scenarios and rely on call-level metrics that fail to capture trajectory-level reasoning quality. To address this gap, we introduce FinTrace, a benchmark comprising 800 expert-annotated trajectories spanning 34 real-world financial task categories across multiple difficulty levels.

### 5. Sell More, Play Less: Benchmarking LLM Realistic Selling Skill

- **arXiv ID:** `2604.07054v2`
- **Date:** 2026-04-08
- **Authors:** Xuanbo Su, Wenhao Hu, Haibo Su, Yunzhang Chen, Le Zhan et al.
- **Categories:** cs.CL
- **Summary:** Sales dialogues require multi-turn, goal-directed persuasion under asymmetric incentives, which makes them a challenging setting for large language models (LLMs). Yet existing dialogue benchmarks rarely measure deal progression and outcomes. We introduce SalesLLM benchmark, a bilingual (ZH/EN) benchmark derived from realistic applications covering Financial Services and Consumer Goods, built from 30,074 scripted configurations and 1,805 curated multi-turn scenarios with controllable difficulty and personas.

### 6. SenseAI: A Human-in-the-Loop Dataset for RLHF-Aligned Financial Sentiment Reasoning

- **arXiv ID:** `2604.05135v1`
- **Date:** 2026-04-06
- **Authors:** Berny Kabalisa
- **Categories:** cs.CL, cs.CE
- **Summary:** We introduce SenseAI, a human-in-the-loop (HITL) validated financial sentiment dataset designed to capture not only model outputs but the full reasoning process behind them. Unlike existing resources, SenseAI incorporates reasoning chains, confidence scores, human correction signals, and real-world market outcomes, providing a structure aligned with Reinforcement Learning from Human Feedback (RLHF) paradigms. The dataset consists of 1,439 labelled data points across 40 US-listed equities and 13 financial data categories, enabling direct integration into modern LLM fine-tuning pipelines.

### 7. Unlocking Data Value in Finance: A Study on Distillation and Difficulty-Aware Training

- **arXiv ID:** `2603.07223v1`
- **Date:** 2026-03-07
- **Authors:** Chuxue Cao, Honglin Lin, Zhanping Zhong, Xin Gao, Mengzhang Cai et al.
- **Categories:** cs.LG
- **Summary:** Large Language Models (LLMs) have demonstrated strong general capabilities, yet their deployment in finance remains challenging due to dense domain-specific terminology, stringent numerical reasoning requirements, and low tolerance for factual errors. We conduct a controlled empirical study showing that in specialized vertical domains, performance is largely determined by the quality and difficulty/verifiability profile of post-training data. We introduce \textbf{ODA-Fin-SFT-318k}, constructed via multi-stage distillation and verification to produce high-quality Chain-of-Thought supervision...

### 8. Agentic AI, Retrieval-Augmented Generation, and the Institutional Turn: Legal Architectures and Financial Governance in the Age of Distributional AGI

- **arXiv ID:** `2603.13244v1`
- **Date:** 2026-02-20
- **Authors:** Marcel Osmond
- **Categories:** cs.CY, cs.AI, cs.CE
- **Summary:** The proliferation of agentic artificial intelligence systems--characterized by autonomous goal-seeking, tool use, and multi-agent coordination--presents unprecedented challenges to existing legal and financial regulatory frameworks. While traditional AI governance has focused on model-level alignment through training-time interventions such as Reinforcement Learning from Human Feedback (RLHF), the deployment of large language models (LLMs) as persistent agents necessitates a paradigm shift toward institutional governance structures. This paper examines the intersection of agentic AI, Retrie...

### 9. QianfanHuijin Technical Report: A Novel Multi-Stage Training Paradigm for Finance Industrial LLMs

- **arXiv ID:** `2512.24314v2`
- **Date:** 2025-12-30
- **Authors:** Shupeng Li, Weipeng Lu, Linyun Liu, Chen Lin, Shaofei Li et al.
- **Categories:** cs.CL
- **Summary:** Domain-specific enhancement of Large Language Models (LLMs) within the financial context has long been a focal point of industrial application. While previous models such as BloombergGPT and Baichuan-Finance primarily focused on knowledge enhancement, the deepening complexity of financial services has driven a growing demand for models that possess not only domain knowledge but also robust financial reasoning and agentic capabilities. In this paper, we present QianfanHuijin, a financial domain LLM, and propose a generalizable multi-stage training paradigm for industrial model enhancement.

### 10. Merging Continual Pretraining Models for Domain-Specialized LLMs: A Case Study in Finance

- **arXiv ID:** `2511.02451v1`
- **Date:** 2025-11-04
- **Authors:** Kentaro Ueda, François Portet, Hirohiko Suwa, Keiichi Yasumoto
- **Categories:** cs.CL
- **Summary:** While LLMs excel at general tasks, they struggle in specialized domains like finance, requiring diverse skills in domain knowledge, mathematical reasoning, and multilingual processing. Merging domain-specific Continual Pre-training (CPT) "experts" offers a practical alternative to costly and unstable multi-skill training. However, unlike established Supervised Fine-Tuning (SFT) model-based merging, CPT model merging remains largely unexplored.

### 11. Fin-Ally: Pioneering the Development of an Advanced, Commonsense-Embedded Conversational AI for Money Matters

- **arXiv ID:** `2509.24342v1`
- **Date:** 2025-09-29
- **Authors:** Sarmistha Das, Priya Mathur, Ishani Sharma, Sriparna Saha, Kitsuchart Pasupa et al.
- **Categories:** cs.AI
- **Summary:** The exponential technological breakthrough of the FinTech industry has significantly enhanced user engagement through sophisticated advisory chatbots. However, large-scale fine-tuning of LLMs can occasionally yield unprofessional or flippant remarks, such as ``With that money, you're going to change the world,'' which, though factually correct, can be contextually inappropriate and erode user trust. The scarcity of domain-specific datasets has led previous studies to focus on isolated components, such as reasoning-aware frameworks or the enhancement of human-like response generation.

### 12. Unlocking Financial Insights: An advanced Multimodal Summarization with Multimodal Output Framework for Financial Advisory Videos

- **arXiv ID:** `2509.20961v1`
- **Date:** 2025-09-25
- **Authors:** Sarmistha Das, R E Zera Marveen Lyngkhoi, Sriparna Saha, Alka Maurya
- **Categories:** cs.CV, cs.AI
- **Summary:** The dynamic propagation of social media has broadened the reach of financial advisory content through podcast videos, yet extracting insights from lengthy, multimodal segments (30-40 minutes) remains challenging. We introduce FASTER (Financial Advisory Summariser with Textual Embedded Relevant images), a modular framework that tackles three key challenges: (1) extracting modality-specific features, (2) producing optimized, concise summaries, and (3) aligning visual keyframes with associated textual points. FASTER employs BLIP for semantic visual descriptions, OCR for textual patterns, and W...

### 13. Towards Secure and Explainable Smart Contract Generation with Security-Aware Group Relative Policy Optimization

- **arXiv ID:** `2509.09942v2`
- **Date:** 2025-09-12
- **Authors:** Lei Yu, Jingyuan Zhang, Xin Wang, Jiajia Ma, Li Yang et al.
- **Categories:** cs.CR, cs.AI, cs.SE
- **Summary:** Smart contracts automate the management of high-value assets, where vulnerabilities can lead to catastrophic financial losses. This challenge is amplified in Large Language Models (LLMs) by two interconnected failures: they operate as unauditable "black boxes" lacking a transparent reasoning process, and consequently, generate code riddled with critical security vulnerabilities. To address both issues, we propose SmartCoder-R1 (based on Qwen2.5-Coder-7B), a novel framework for secure and explainable smart contract generation.

### 14. MM-DREX: Multimodal-Driven Dynamic Routing of LLM Experts for Financial Trading

- **arXiv ID:** `2509.05080v2`
- **Date:** 2025-09-05
- **Authors:** Yang Chen, Yueheng Jiang, Zhaozhao Ma, Yuchen Cao, Jacky Keung et al.
- **Categories:** q-fin.TR
- **Summary:** The inherent non-stationarity of financial markets and the complexity of multi-modal information pose significant challenges to existing quantitative trading models. Traditional methods relying on fixed structures and unimodal data struggle to adapt to market regime shifts, while large language model (LLM)-driven solutions - despite their multi-modal comprehension - suffer from static strategies and homogeneous expert designs, lacking dynamic adjustment and fine-grained decision mechanisms. To address these limitations, we propose MM-DREX: a Multimodal-driven, Dynamically-Routed EXpert fram...

### 15. Select to Know: An Internal-External Knowledge Self-Selection Framework for Domain-Specific Question Answering

- **arXiv ID:** `2508.15213v2`
- **Date:** 2025-08-21
- **Authors:** Bolei He, Xinran He, Run Shao, Shanfu Shu, Xianwei Xue et al.
- **Categories:** cs.CL
- **Summary:** Large Language Models (LLMs) perform well in general QA but often struggle in domain-specific scenarios. Retrieval-Augmented Generation (RAG) introduces external knowledge but suffers from hallucinations and latency due to noisy retrievals. Continued pretraining internalizes domain knowledge but is costly and lacks cross-domain flexibility.

---

## Query 3: Qwen Agent / Scope Framework / Tool-Calling

**Query:** `all:(qwen AND (agent OR scope) AND framework AND tool-calling)`  |  **Results:** 3

### 1. TinyLLM: Evaluation and Optimization of Small Language Models for Agentic Tasks on Edge Devices

- **arXiv ID:** `2511.22138v1`
- **Date:** 2025-11-27
- **Authors:** Mohd Ariful Haque, Fahad Rahman, Kishor Datta Gupta, Khalil Shujaee, Roy George
- **Categories:** cs.LG
- **Summary:** This paper investigates the effectiveness of small language models (SLMs) for agentic tasks (function/tool/API calling) with a focus on running agents on edge devices without reliance on cloud infrastructure. We evaluate SLMs using the Berkeley Function Calling Leaderboard (BFCL) framework and describe parameter-driven optimization strategies that include supervised fine-tuning (SFT), parameter-efficient fine-tuning (PEFT), reinforcement learning (RL)-based optimization, preference alignment via Direct Preference Optimization (DPO), and hybrid methods. We report results for models including...

### 2. AgentFlux: Decoupled Fine-Tuning & Inference for On-Device Agentic Systems

- **arXiv ID:** `2510.00229v4`
- **Date:** 2025-09-30
- **Authors:** Rohan Kadekodi, Zhan Jin, Keisuke Kamahori, Yile Gu, Sean Khatiri et al.
- **Categories:** cs.AI, cs.LG
- **Summary:** The deployment of Large Language Models (LLMs) as agentic orchestrators has revolutionized task automation, but the need for privacy-preserving, cost-effective solutions demands on-device inference capabilities. However, local LLMs consistently underperform compared to frontier models in tool calling scenarios, struggling with both tool selection from large tool sets and accurate argument generation for complex parameter structures. We introduce a methodology that disaggregates a tool-calling task into two distinct subtasks: tool selection and argument generation.

### 3. Acting Less is Reasoning More! Teaching Model to Act Efficiently

- **arXiv ID:** `2504.14870v2`
- **Date:** 2025-04-21
- **Authors:** Hongru Wang, Cheng Qian, Wanjun Zhong, Xiusi Chen, Jiahao Qiu et al.
- **Categories:** cs.AI, cs.CL
- **Summary:** Tool-integrated reasoning (TIR) augments large language models (LLMs) with the ability to invoke external tools during long-form reasoning, such as search engines and code interpreters, to solve tasks beyond the capabilities of internal reasoning. While reinforcement learning (RL) has shown promise in training such agents, most of existing approaches typically optimize only for final correctness without considering the efficiency or necessity of external tool use. This often leads to excessive tool calling, incurring high computational costs and hindering the development of internal reasoni...
