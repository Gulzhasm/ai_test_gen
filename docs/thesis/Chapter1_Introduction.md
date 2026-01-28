# Chapter 1

# Introduction

## 1.1 Background and Motivation

The software industry has witnessed unprecedented growth in application complexity over the past decade. Modern software systems are no longer standalone applications but intricate ecosystems comprising microservices, third-party integrations, and multi-platform deployments. This complexity presents significant challenges for quality assurance teams, who must ensure that every feature functions correctly across diverse environments and user scenarios.

At the heart of quality assurance lies the test case—a documented set of conditions, actions, and expected outcomes designed to verify that a software feature behaves as intended. Despite decades of advancement in test automation tools, the creation of test cases themselves remains a predominantly manual endeavor. Quality assurance engineers spend considerable time translating user requirements into detailed test procedures, a process that is both time-intensive and prone to inconsistency.

The emergence of Agile and DevOps methodologies has further intensified this challenge. With development cycles shrinking from months to weeks or even days, the traditional approach of manually crafting test cases struggles to keep pace. Teams find themselves caught in a perpetual bottleneck: features are developed rapidly, but comprehensive test coverage lags behind, creating quality risks that can manifest as bugs in production, customer dissatisfaction, and costly rework.

This research is motivated by a fundamental question: Can artificial intelligence bridge the gap between the speed of modern software development and the thoroughness required for quality assurance? More specifically, can Large Language Models, with their remarkable ability to understand and generate human-like text, be harnessed to automate the creation of test cases from natural language requirements?

## 1.2 The Current State of Test Automation

To appreciate the significance of this research, it is essential to understand what test automation currently encompasses and where its limitations lie. Contemporary test automation predominantly focuses on test *execution*—the running of predefined tests against software builds. Tools such as Selenium, Cypress, and Playwright have revolutionized how organizations execute regression tests, enabling thousands of test scenarios to run unattended overnight.

However, these tools share a common prerequisite: someone must first *design* the tests. The test scripts that automation frameworks execute are translations of manually conceived test cases into code. This distinction between test execution and test design is crucial. While the industry has largely solved the problem of running tests automatically, the problem of *creating* tests automatically—what might be called the "last mile" of test automation—remains largely unsolved.

Enterprise Application Lifecycle Management tools such as Azure DevOps, Jira, and TestRail provide sophisticated platforms for managing test cases, tracking their execution, and reporting results. Yet these platforms, too, assume that test cases arrive fully formed, authored by human engineers. The intellectual labor of analyzing requirements, identifying test scenarios, and articulating step-by-step procedures continues to rest on human shoulders.

## 1.3 The Promise and Limitations of Large Language Models

The advent of Large Language Models has sparked considerable interest in their application to software engineering tasks. Models such as GPT-4, Claude, and their successors have demonstrated impressive capabilities in understanding code, generating documentation, and even writing functional programs. These capabilities naturally invite speculation about their potential for test case generation.

Initial experiments with LLM-based test generation have yielded promising but inconsistent results. When provided with a user story or requirement specification, modern LLMs can produce test cases that superficially resemble human-authored ones. They understand the general structure of a test case, can generate plausible test steps, and often identify obvious scenarios to verify.

However, closer examination reveals significant limitations. Generic LLM outputs frequently lack application-specific context—they produce test cases that might apply to any software application rather than the specific one under test. The formatting and structure of generated tests varies unpredictably between invocations. Critical edge cases that an experienced QA engineer would instinctively include are often absent. Perhaps most problematically, LLMs occasionally "hallucinate" features or behaviors that do not exist in the target application, producing test cases that are not merely unhelpful but actively misleading.

These limitations suggest that purely LLM-based approaches, while promising, are insufficient for production-quality test case generation. The models lack the domain knowledge that experienced QA engineers possess—knowledge about specific applications, their constraints, their common failure modes, and the organizational standards for test documentation.

## 1.4 Problem Statement

This research addresses a critical gap in software quality assurance: the absence of an effective, automated approach to generating high-quality test cases from natural language requirements. Manual test case creation presents several interrelated problems that this research seeks to address.

First, the process is inherently time-consuming. Industry estimates suggest that creating comprehensive test cases for a single user story requires between two and four hours of skilled QA engineer time. For organizations managing hundreds of user stories per release cycle, this translates to thousands of engineering hours devoted solely to test documentation.

Second, the quality of manually created test cases varies significantly across team members. Senior engineers with deep domain knowledge produce thorough, well-structured tests, while less experienced team members may miss critical scenarios or produce inconsistent documentation. This variability undermines the reliability of the overall test suite.

Third, domain expertise tends to remain siloed within individual engineers' minds rather than being systematically captured and applied. When experienced team members leave or change roles, their accumulated knowledge about effective testing strategies often departs with them.

Fourth, pure LLM-based solutions, despite their promise, fall short of production requirements. They generate outputs that require substantial human review and correction, negating much of their time-saving potential. Their inconsistency makes them difficult to integrate into existing quality assurance workflows.

The research gap this thesis addresses lies at the intersection of rule-based systems and machine learning approaches. While each approach has been studied independently, their combination for test case generation remains underexplored. Furthermore, existing research has largely focused on generating test *code* for unit testing, leaving the domain of manual functional test cases—which remain prevalent in enterprise software development—relatively neglected.

## 1.5 Research Objectives

This research aims to design, implement, and evaluate a hybrid framework for AI-driven test case generation that combines rule-based systems with Large Language Models. The primary objective is to produce test cases that match or exceed the quality of manually authored tests while significantly reducing creation time.

This overarching goal encompasses several specific objectives. The first objective is to develop a project-agnostic architecture that can be configured for different applications without requiring code modifications. This adaptability is essential for practical adoption, as organizations rarely use a single software application.

The second objective is to create dynamic prompt engineering techniques that effectively inject domain knowledge into LLM interactions. Rather than relying on generic prompts, the framework should construct prompts that incorporate application-specific terminology, constraints, and testing patterns.

The third objective is to achieve seamless integration with Azure DevOps, recognizing that test cases exist within a broader ecosystem of requirements management, test planning, and execution tracking. A solution that operates in isolation from these systems offers limited practical value.

The fourth objective is to demonstrate measurable quality improvements over baseline approaches, including both manual test creation and pure LLM generation. Quality must be assessed through multiple dimensions: completeness of coverage, consistency of formatting, relevance of scenarios, and accuracy of expected outcomes.

The fifth objective is to achieve significant time savings—targeting at least a sixty percent reduction in test case creation time compared to fully manual approaches.

## 1.6 Research Questions

This thesis is guided by one primary research question and four supporting questions that together define the scope and direction of the investigation.

The primary research question asks: How can a hybrid approach combining rule-based generation with LLM correction produce test cases that match or exceed the quality of manually created test cases while significantly reducing creation time?

This central question is supported by four subsidiary inquiries. The first asks what rule-based heuristics are most effective for initial test case scaffolding. Understanding which aspects of test case structure can be reliably generated through deterministic rules is essential for designing an efficient hybrid architecture.

The second supporting question investigates how prompts should be structured to leverage LLM capabilities while avoiding common pitfalls such as hallucination and inconsistency. Prompt engineering has emerged as a critical discipline in applied AI, and its principles must be adapted to the specific domain of test case generation.

The third supporting question explores what metrics best capture test case quality for the purpose of comparing generated and manual tests. Quality assessment in software testing is inherently multidimensional, and establishing appropriate evaluation criteria is essential for meaningful research conclusions.

The fourth supporting question examines how the hybrid approach compares to pure LLM generation in terms of cost, quality, and consistency. This comparison illuminates the specific value added by the rule-based component and informs decisions about architectural balance.

## 1.7 Scope and Delimitations

This research focuses on the generation of manual functional test cases—documented procedures intended for human execution during software testing. This focus deliberately excludes automated test script generation, which represents a distinct technical challenge involving code synthesis rather than natural language documentation.

The input to the proposed framework consists of user stories retrieved from Azure DevOps, including their associated acceptance criteria and QA preparation notes. This input source reflects the common practice in enterprise software development of documenting requirements in structured formats within Application Lifecycle Management tools.

The primary case study for this research is ENV QuickDraw, a desktop application deployed across Windows, iPad, and Android tablet platforms. While this single case study limits immediate generalizability claims, it provides sufficient depth for thorough investigation and the framework's project-agnostic design facilitates future extension to other applications.

Several areas fall explicitly outside this research's scope. Performance testing, security testing, and load testing each involve specialized methodologies and tools that warrant separate investigation. Mobile-specific testing patterns, beyond tablet applications, are similarly excluded. The research does not address test execution or reporting, focusing exclusively on test case creation.

The research acknowledges several inherent limitations. Findings derived from a single case study require validation across additional applications before broad generalization. The framework depends on LLM API availability and pricing, which may change over time. Quality evaluation necessarily involves subjective human judgment, introducing potential variability in assessment. Finally, the research is limited to English-language requirements, with multilingual support remaining a topic for future work.

## 1.8 Significance and Contributions

This research makes contributions across academic, practical, and industrial dimensions. From an academic perspective, the thesis introduces a novel hybrid architecture that combines rule-based systems with Large Language Models for test case generation. This architecture represents a new approach to the longstanding challenge of test automation, demonstrating that deterministic and probabilistic methods can be synergistically combined.

The research also contributes a dynamic prompt engineering framework that incorporates project-specific context into LLM interactions. This framework advances understanding of how domain knowledge can be effectively communicated to general-purpose language models, a question with implications beyond software testing.

Additionally, the thesis proposes a quality metrics framework specifically designed for evaluating generated test cases. This framework addresses a gap in existing literature, which has focused primarily on metrics for generated code rather than generated documentation.

The empirical comparison between hybrid and pure LLM approaches provides evidence for the value of hybrid architectures in applied AI systems—a finding with potential relevance to numerous other domains where AI augmentation is being explored.

From a practical standpoint, the research produces an open-source framework suitable for deployment in enterprise environments. This framework is accompanied by a project-agnostic configuration system that enables adaptation to different applications through YAML configuration files rather than code modifications.

The integration patterns developed for Azure DevOps serve as templates for connecting AI-powered generation tools with existing enterprise infrastructure. The demonstrated cost reduction compared to pure LLM generation—estimated at fifty percent—enhances the economic viability of AI-assisted testing approaches.

For the software industry more broadly, this research offers a template for AI augmentation in software engineering workflows. As organizations increasingly explore how artificial intelligence can enhance developer and tester productivity, this thesis provides concrete evidence of both possibilities and limitations.

## 1.9 Thesis Structure

This thesis is organized into eight chapters that together present a comprehensive investigation of AI-driven test case generation.

Chapter 2 presents a literature review examining prior research in automated test generation, the application of Large Language Models to software engineering, and the emerging discipline of prompt engineering. This review establishes the theoretical foundation for the proposed hybrid approach and identifies the specific gaps this research addresses.

Chapter 3 describes the research methodology, including the overall research design, the hybrid architecture's conceptual framework, and the approach taken for implementation and evaluation. This chapter justifies the methodological choices made and addresses potential threats to validity.

Chapter 4 details the system design, presenting the framework's architecture, its constituent components, and the patterns employed for integration with Azure DevOps. This chapter provides the technical foundation necessary for understanding the implementation.

Chapter 5 covers the implementation, including the technical details of the rule-based generators, the prompt engineering techniques developed, and the LLM integration approach. This chapter bridges design and realization, documenting how conceptual elements were translated into working software.

Chapter 6 presents the evaluation, describing the experiments conducted, the metrics employed, and the results obtained. This chapter provides the empirical evidence necessary for assessing the framework's effectiveness.

Chapter 7 offers a discussion of the findings, interpreting results in light of the research questions, exploring implications for practice and theory, and acknowledging threats to validity. This chapter synthesizes empirical results with broader considerations.

Chapter 8 concludes the thesis with a summary of contributions, reflection on limitations, and recommendations for future research directions.

## 1.10 Chapter Summary

This chapter has introduced the research problem motivating this thesis: the challenge of automating test case creation in an era of accelerating software development. It has situated this problem within the context of current test automation practices, which excel at test execution but struggle with test design. The promise and limitations of Large Language Models for this task have been examined, revealing the need for hybrid approaches that combine AI capabilities with structured domain knowledge.

The research objectives, questions, and scope have been defined, establishing clear boundaries for the investigation. The significance of this work has been articulated across academic, practical, and industrial dimensions. Finally, the thesis structure has been outlined to guide the reader through the subsequent chapters.

The following chapter examines the existing literature relevant to this research, establishing the theoretical foundations upon which the proposed framework is built.
