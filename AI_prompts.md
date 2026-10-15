# AI Prompts

A running log of the prompts I gave my AI coding assistant while building the Campus Customs multi-agent operations system. Each problem gets its own section. Follow-up prompts appear under the original prompt, with a short note on what the first attempt was missing.

---

## Problem 1: Vibe Coder Prompts

### Initial prompt

> I'm working on a multi-agent AI application for Campus Customs, and I want to keep a clear record of how I use AI coding assistance throughout the project.
> Please create a Markdown file named `AI_prompts.md` in the root directory of my project.
> I want this file to serve as a running log of the instructions I give you while working through the assignment's 11 problems.
> Please organize the document as follows:
>
> 1. Create a separate section for each problem, using its number and title as the heading.
> 2. Record at least one prompt that I actually provided for each problem, keeping my original wording whenever possible.
> 3. If I provide additional instructions to improve or correct the initial implementation, include one follow-up prompt.
> 4. For each follow-up, briefly explain what was missing or needed improvement after the initial attempt.
> 5. Keep the document organized and easy to read using Markdown formatting.
>
> Start by creating the file and adding a section for Problem 1, titled "Vibe Coder Prompts." Include this initial request as the first recorded prompt.
> As we work through the remaining problems, please update the file with the actual prompts I provide. Do not invent prompts or fill in sections for problems we haven't started.
> For now, focus only on setting up this documentation file. Do not implement other parts of the application yet.

---

## Problem 2: Study the Campus Customs Database

### Initial prompt

> I want to understand the database structure of the Campus Customs project before building the multi-agent system.
> Please help me with the following tasks:
>
> 1. Explore the database: Open `data/campus_customs.db` and examine all the tables, including their column names, data types, and relationships. I want to understand what information is stored in each table and how the data supports the shop's daily operations.
> 2. Create a working database: Make a copy of the original database and save it as `data/campus_customs_new.db`. Keep the original database unchanged, since we will use it to reset the system later. All future database updates should happen in the new copy.
> 3. Analyze the open tickets: Find the three open tickets in the database and review their details. Explain how each ticket relates to other tables, such as inventory, vendors, invoices, payments, or leases. Identify which information the agents will need to resolve each ticket.
> 4. Document the database: Create a Markdown file at `output/harness.md`. For every table, include:
>    * Table name
>    * All column names and their data types
>    * A brief explanation of what the table contains
>    * One sentence explaining why the table is useful for the multi-agent system
> 5. Summarize the findings: Provide a short overview of the database structure, the relationships between important tables, and how different agents might use this information to complete their tasks.
>
> Please make the documentation clear and easy to follow, since we will continue expanding `output/harness.md` as we work through the remaining problems.
> For now, focus only on understanding and documenting the database. Do not build the MCP server, backend, or frontend yet.
> Also, please add this prompt to `AI_prompts.md` under Problem 2: Study the Campus Customs Database.

---

## Problem 3: Build the MCP Server

### Initial prompt

> I'm ready to build the MCP server for my Campus Customs multi-agent project.
> Please create an MCP server using FastMCP inside the `mcp_server/` directory. The server should connect to `data/campus_customs_new.db`, which is the working database we created earlier. Make sure the original database remains unchanged.
> For this step, I only want to implement the server and define three useful MCP tools. There is no need to start the server or integrate it with the AI agents yet.
>
> 1. Build the MCP Server
>
> * Use FastMCP to create the server.
> * Configure the database connection to use the working SQLite database.
> * Organize the code so additional tools can be added easily in future problems.
> * Use clear and descriptive names for the tools.
> * Make sure all information comes directly from the database rather than using hardcoded or invented values.
>
> 2. Implement Three MCP Tools
>
> Review the three existing tickets (101, 102, and 103) and their related database records.
> Based on the specific requirements of each ticket, create three MCP tools that help agents retrieve the information needed to resolve those issues.
> Each tool should:
>
> * Have a clear name that describes its function.
> * Access the appropriate database tables.
> * Return relevant information in a structured format.
> * Include basic error handling for missing or invalid records.
> * Be designed so any agent can use it later.
>
> Choose the tools based on the actual ticket details rather than making assumptions about what the tickets contain.
>
> 3. Update the Project Documentation
>
> Expand the existing `output/harness.md` file with a new section describing the three MCP tools.
> For each tool, document:
>
> * The tool name and its purpose.
> * The database table or tables it reads.
> * The specific ticket it supports (101, 102, or 103).
> * A short explanation of how the tool helps address that ticket's requirements.
>
> Please make the explanations specific to the actual tickets rather than using generic descriptions.
>
> 4. Create an MCP Server README
>
> Add a `mcp_server/README.md` file that explains:
>
> * The purpose of the MCP server.
> * The database file it connects to.
> * The three available tools and what each one does.
> * How the server fits into the overall multi-agent architecture.
>
> 5. Maintain the AI Prompt Log
>
> Add this request to `AI_prompts.md` under "Problem 3: Build the MCP Server."
> Keep the original wording of the prompt so the file accurately reflects the instructions I provided.
>
> Important Constraints
>
> * Use FastMCP for the implementation.
> * Work only with `data/campus_customs_new.db`.
> * Do not modify the original database.
> * Do not fabricate database records or ticket details.
> * Do not implement additional MCP tools beyond the three required at this stage.
> * Do not start the server or connect it to the FastAPI backend yet.
>
> For now, focus only on completing Problem 3. Keep the implementation simple, modular, and easy to extend in later steps.

---

## Problem 4: Connect the MCP Server and Test Each Tool

### Initial prompt

> I'm ready to connect the MCP server we built in Problem 3 to my AI coding environment and verify that all three tools work correctly.
> Please help me complete the following steps:
>
> 1. Configure the MCP Connection
>
> * Connect the existing MCP server in `mcp_server/` to my current coding environment so the AI assistant can discover and use its tools.
> * Create a `.mcp.json` configuration file in the project root, or use the appropriate local MCP configuration format supported by my coding environment.
> * Make sure the configuration points to the correct server entry point and uses the project's Python environment.
> * Confirm that the server accesses `data/campus_customs_new.db` rather than the original database.
>
> 2. Test All Three MCP Tools
>
> Once the connection is established, use the AI coding assistant to invoke each of the three tools created in Problem 3.
> For each tool:
>
> * Write a natural-language request that triggers the tool.
> * Record the exact prompt used to request the information.
> * Capture the tool name that was invoked.
> * Save the actual response returned by the tool.
> * Compare the returned values with the working SQLite database to verify accuracy.
>
> Please use real database records and do not generate sample or fabricated responses.
>
> 3. Save the Test Results
>
> Create a JSON file at `output/mcp_smoke.json` containing the test evidence for all three tools.
> For each test, include:
>
> * `prompt`: The natural-language instruction used to call the tool.
> * `tool_name`: The name of the MCP tool that was executed.
> * `tool_output`: The actual response returned by the tool.
>
> Make sure the JSON is properly formatted and contains three test records, one for each MCP tool.
>
> 4. Verify the Integration
>
> Check that:
>
> * The AI coding assistant can successfully connect to the MCP server.
> * All three tools are discoverable and callable.
> * Each tool returns the expected database information.
> * The results match the values stored in `data/campus_customs_new.db`.
> * No changes are made to the original database.
>
> If any connection or tool execution fails, identify the issue, correct it, and test again.
>
> 5. Update the Prompt Log
>
> Add this request to `AI_prompts.md` under "Problem 4: Connect the MCP Server and Test Each Tool."
> Record any additional prompts used to troubleshoot or fix problems, along with a brief explanation of what was missing or incorrect in the initial attempt.
> For now, focus only on MCP integration and testing. Do not start implementing the FastAPI backend, AI agent orchestration, or React dashboard.
> Please report the results of all three tests and confirm which files were created or updated. Do not claim a test passed unless the MCP tool was actually invoked and its output verified.

### Follow-up prompt

**What was missing:** The first attempt created `.mcp.json` and confirmed the server starts from it, but `output/mcp_smoke.json` was never produced. The coding session had been opened on the parent folder, so Claude Code never loaded `HW 5/.mcp.json` and couldn't call the tools itself. The fix was a new Claude Code session opened in `HW 5`, where the `campus-customs` server loaded. That session called `check_stock_and_vendor_status`, `get_lease_payment_status` and `evaluate_bulk_discount` directly, saved the real outputs to `output/mcp_smoke.json`, and passed all 23 checks in `scripts/verify_mcp_smoke.py` (every value re-queried from `data/campus_customs_new.db`; original DB unchanged).

> fix it

---

## Problem 5: Build the Agent Team and Expand MCP Tools

### Initial prompt

> I'm ready to build the multi-agent system for Campus Customs and expand the MCP server we created in the previous steps.
> Please focus on implementing the five AI agents, enabling collaboration between them, and adding the MCP tools needed to handle the existing business tickets.
>
> 1. Build the Multi-Agent Team
>
> Use PydanticAI to create five specialized agents:
>
> * Boss Agent: Reviews incoming tickets, determines priorities, delegates tasks to other agents, coordinates their work, and makes final decisions.
> * Inventory Agent: Checks stock availability by product and size, identifies shortages, reviews supplier options, and determines potential restocking solutions.
> * Accounting Agent: Reviews cash balances, outstanding invoices, product margins, and payment obligations. It can prepare payment requests and purchase orders but must obtain human approval before executing payments.
> * Facilities Agent: Handles store-related operational issues, including lease agreements, rental obligations, and facility expenses.
> * Customer Service Agent: Handles customer inquiries, prepares responses, and coordinates with other agents to provide accurate information. Messages must remain as drafts rather than being sent externally.
>
> 2. Enable Full Agent Collaboration
>
> Design the system so all five agents can communicate and delegate tasks to one another.
> Each agent should be able to:
>
> * Request assistance from any other agent.
> * Share relevant findings and task context.
> * Return structured results to the requesting agent.
> * Participate in multi-step workflows when a ticket requires multiple areas of expertise.
>
> Implement agent execution loops and delegation logic using PydanticAI.
> Avoid unnecessary repeated delegation and establish reasonable limits to prevent infinite loops or excessive token consumption.
>
> 3. Organize the Backend Code
>
> Use the following project structure:
>
> * `backend/prompts/`: Store a separate instruction file for each of the five agents.
> * `backend/models.py`: Define the structured data models and shared data types.
> * `backend/`: Store agent implementations, orchestration logic, and supporting modules.
>
> Write detailed, role-specific instructions for each agent.
> Each prompt should clearly describe the agent's responsibilities, available tools, collaboration rules, decision-making boundaries, and relevant shop policies.
> Avoid generic instructions. Make sure the prompts reflect the actual Campus Customs business scenario.
>
> 4. Configure the AI Model
>
> All agents must use `gpt-6-luna` through Portkey.
> Use the `PORTKEY_API_KEY` environment variable for authentication.
> Do not use any other AI model, and do not expose API credentials in the source code.
> Keep model usage efficient by minimizing redundant calls, limiting unnecessary agent interactions, and reusing information already retrieved when appropriate.
>
> 5. Expand the MCP Server
>
> Review tickets 101, 102, and 103 and identify any additional MCP tools needed for the agents to complete their work.
> Extend the existing MCP server with those tools while keeping the original three tools functional.
> Important requirements:
>
> * All shop-related information must come from `data/campus_customs_new.db`.
> * Agents must access shop data through MCP tools.
> * Do not create a separate database access layer in the backend that bypasses MCP.
> * Use meaningful tool names and structured responses.
> * Validate inputs and handle missing or invalid database records.
> * Implement database updates only when permitted by the relevant business rules.
>
> 6. Implement Business Safety Rules
>
> Make sure the agent system follows these constraints:
>
> * Require explicit human approval before any payment is executed.
> * Reject payments that would result in a negative cash balance.
> * Verify outstanding vendor invoices before initiating new purchase orders.
> * Use `desk.date_today` as the official business date.
> * Retrieve vendor lead times from the database.
> * Never assume incoming revenue or additional cash.
> * Never send actual customer emails or contact external vendors.
> * Keep customer communications as drafts.
> * Prevent unauthorized database changes and repeated payment execution.
>
> 7. Implement an Audit Trail
>
> Create an append-only audit log at:
> `output/audit_trail.json`
> Record each meaningful step in the agent execution process, including:
>
> * Timestamp
> * Agent name
> * Ticket ID
> * Action or decision
> * MCP tool used, if applicable
> * Delegation target, if applicable
> * Relevant inputs and outputs
> * Execution status and any errors
>
> The audit trail should make it possible to understand how agents collaborate and how decisions are made.
> Do not overwrite existing records when the system runs again. Preserve previous execution history.
>
> 8. Update Project Documentation
>
> Expand `output/harness.md` to include:
>
> * All five agents and their responsibilities.
> * Every MCP tool, including the tools added in this problem.
> * The database tables accessed by each tool.
> * How agents collaborate and delegate tasks.
> * A short safety section covering financial approvals, data integrity, customer communication restrictions, and token usage limits.
>
> Also update `mcp_server/README.md` so the documented tool list matches the actual implementation.
>
> 9. Update the AI Prompt Log
>
> Add this request to `AI_prompts.md` under:
> Problem 5: Build the Agent Team and Expand MCP Tools
> Include any follow-up instructions I provide during development, along with a brief explanation of what needed improvement.
>
> 10. Validate the Implementation
>
> Before finishing, verify that:
>
> * All five agents are implemented using PydanticAI.
> * Every agent uses `gpt-6-luna` through Portkey.
> * Agents can delegate work to one another.
> * All shop data access goes through the MCP server.
> * The expanded MCP tools support the existing tickets.
> * Audit logs are appended rather than overwritten.
> * Safety rules are enforced for payments and other sensitive actions.
> * Documentation reflects the actual implementation.
>
> For now, focus only on Problem 5. Do not build the React dashboard or implement unrelated features from later problems.
> Please summarize the files created or modified, the agents and MCP tools implemented, and any remaining issues that require attention.

---

## Problem 6: Plan the Three Tickets

### Initial prompt

> I'm ready to plan how the Campus Customs multi-agent team should handle the three open tickets before connecting and running the backend.
> Please help me create a clear plan for tickets 101, 102, and 103 based on their actual details in the working database.
>
> 1. Review the Three Tickets
>
> Start by reviewing the three open tickets in `data/campus_customs_new.db` using the existing MCP tools.
> For each ticket, identify the business issue, the information needed to resolve it, and which agents should be involved.
> Use only the actual database information and existing MCP tools. Do not make assumptions about missing data.
>
> 2. Create an HTML Planning Page
>
> Create a standalone HTML file at:
> `output/desk_tickets.html`
> The page should open directly in a web browser without requiring a running backend or web server.
> Include five navigation tabs:
>
> * Ticket 101
> * Ticket 102
> * Ticket 103
> * Cash
> * Reflection
>
> For now, leave the Cash and Reflection tabs empty or display a short "Coming Later" message, since they will be completed in future problems.
>
> 3. Develop an Expected Plan for Each Ticket
>
> Each ticket tab should contain an "Expected" section describing how I think the agents should collaborate to resolve that ticket.
> For each ticket, explain:
>
> Initial Assignment
>
> * Which specialist the Boss Agent should contact first.
> * Why that specialist is the most appropriate starting point.
>
> Agent Collaboration
>
> * The sequence of agent delegations expected during the workflow.
> * Which agent should request help from another agent and why.
> * How the agents should share findings and coordinate their decisions.
> * Only involve agents whose expertise is relevant to the specific ticket.
>
> MCP Tool Usage
>
> * Which existing MCP tools the agents are expected to call.
> * What information each tool should retrieve or update.
> * How the tool results will help agents decide what to do next.
>
> Expected Outcome
>
> * What a successful resolution should look like.
> * Whether any human approval will be necessary.
> * What database records or customer-facing drafts may need to be updated.
>
> Make each plan specific to the actual ticket rather than using the same generic workflow for all three.
>
> 4. Reserve Space for Actual Results
>
> Add an "Actual" section to each ticket tab, but leave it empty for now.
> We will complete these sections after running the agents in a later problem and compare their actual behavior against the original expectations.
> Do not execute the agents or generate simulated results at this stage.
>
> 5. Keep the Interface Simple
>
> Make the HTML page easy to navigate and read.
> Use a clean layout with clearly labeled tabs and separate sections for expected and actual results.
> The page should work locally by double-clicking the HTML file.
>
> 6. Update the Prompt Log
>
> Add this request to `AI_prompts.md` under:
> Problem 6: Plan the Three Tickets
> Record the prompt I used and any follow-up instructions needed to improve the initial output.
>
> 7. Validate the Deliverable
>
> Before finishing, confirm that:
>
> * `output/desk_tickets.html` has been created.
> * All five tabs are present and functional.
> * Tickets 101, 102, and 103 each have a detailed Expected section.
> * Each plan identifies the first agent, subsequent delegations, and relevant MCP tools.
> * Agent involvement is tailored to the actual business issue.
> * The Actual sections remain empty.
> * The Cash and Reflection tabs are reserved for future work.
> * No agent execution or database modifications have occurred.
>
> For now, focus only on planning the workflows and creating the HTML page. Do not implement the actual ticket-resolution process yet.

---

## Problem 7: Backend Routes

### Initial prompt

> I'm ready to build the FastAPI backend for my Campus Customs multi-agent application.
> I have already created the MCP server and five AI agents in the previous steps. Now I want to expose the necessary backend APIs so the React dashboard can interact with the agent system.
> Please focus on implementing the backend routes in `backend/main.py` and connecting them to the existing components.
>
> 1. Set Up the FastAPI Application
>
> Create a FastAPI application in `backend/main.py`.
> Make sure the backend can communicate with the existing multi-agent system and access shop information through the MCP server.
> The backend should use `data/campus_customs_new.db` as the working database, with business data access handled through MCP tools rather than creating a separate database access layer.
> Configure the application so it can be accessed locally at `http://localhost:8000`.
>
> 2. Implement the Required API Routes
>
> Please create endpoints that support the following operations:
>
> A. Retrieve Tickets
>
> Create an endpoint that returns tickets 101, 102, and 103, including their current status.
> The response should indicate whether each ticket is open or resolved, along with relevant ticket information.
>
> B. Run Agents on a Ticket
>
> Create an endpoint that accepts a ticket ID and starts the existing multi-agent workflow for that specific ticket.
> The Boss Agent should coordinate the process and delegate tasks to the appropriate specialists.
> Return the execution result and updated ticket status when available.
>
> C. Retrieve Agent Activity
>
> Create an endpoint that returns recent agent events, including:
>
> * Which agent performed the action.
> * What the agent said or decided.
> * Which MCP tools were used.
> * Any delegation between agents.
> * The execution status.
>
> Use the existing audit trail so the frontend can display agent activities and refresh the information.
>
> D. Approve Payments or Purchases
>
> Create an endpoint that allows a human user to approve a pending payment or purchase request.
> Agents should only prepare financial transactions. The actual payment must happen after the user explicitly approves it through this endpoint.
> Before executing a payment:
>
> * Verify that the request is valid and still pending.
> * Confirm sufficient cash is available.
> * Reject transactions that would create a negative balance.
> * Prevent duplicate payments.
> * Update the relevant database records through the MCP server.
> * Record the approval and transaction in the audit trail.
>
> E. Retrieve Cash Balance
>
> Create an endpoint that returns the current checking account balance from the `cash_accounts` table.
> The balance must reflect any approved payments that have already been executed.
>
> F. Reset the Database
>
> Create an endpoint that restores `data/campus_customs_new.db` to the original values stored in `data/campus_customs.db`.
> This should allow me to restart the ticket-resolution process from a clean state without modifying the original database.
> Make sure the reset operation is explicit and does not happen automatically during normal ticket processing.
>
> 3. Use Structured API Responses
>
> Define appropriate request and response models using Pydantic.
> Use clear JSON response formats so the React frontend can easily consume the API.
> Include validation and error handling for:
>
> * Invalid ticket IDs.
> * Missing records.
> * Failed agent executions.
> * Invalid or duplicate payment approvals.
> * Insufficient cash balances.
> * Database or MCP connection failures.
>
> 4. Support Frontend Integration
>
> Configure CORS for the local React development environment.
> Make sure the backend routes are designed to support:
>
> * Displaying ticket statuses.
> * Starting ticket workflows.
> * Refreshing agent activity.
> * Reviewing and approving payments.
> * Monitoring cash balances.
> * Resetting the simulation.
>
> 5. Run and Test the Backend
>
> The application should be able to start from the `backend/` directory using:
> `uvicorn main:app --reload --port 8000`
> Once started, the API should be accessible at:
> `http://localhost:8000`
> Test the endpoints and confirm they return valid responses.
> For operations that modify data, use controlled tests and verify that the working database is updated correctly without changing the original database.
> Do not execute real payments or external communications.
>
> 6. Update the Documentation
>
> Expand `output/harness.md` with a section describing the backend API routes.
> For each endpoint, include:
>
> * HTTP method.
> * URL path.
> * Purpose of the endpoint.
> * Expected inputs and outputs.
>
> Also add this request to `AI_prompts.md` under:
> Problem 7: Backend Routes
> Record any follow-up prompts used to fix or improve the implementation.
>
> 7. Validate the Implementation
>
> Before finishing, confirm that:
>
> * The FastAPI application starts successfully.
> * All six required backend capabilities are implemented.
> * Ticket execution uses the existing multi-agent system.
> * Business data access goes through MCP.
> * Agent events are available to the frontend.
> * Payments require explicit human approval.
> * Cash balances cannot become negative.
> * The database can be reset to its original state.
> * The API routes are documented in `output/harness.md`.
>
> For now, focus only on the backend API. Do not build the React dashboard yet.
> Please summarize the implemented routes, test results, and files created or modified.

---

## Problem 8: Agent Dashboard

### Initial prompt

> I'm ready to build the frontend dashboard for my Campus Customs multi-agent application.
> I have already developed the MCP server, five AI agents, and FastAPI backend. Now I want to create a polished, interactive dashboard that allows a human operator to manage tickets, monitor agent activities, and approve financial transactions.
> Please focus on implementing Problem 8 using React, Vite, and TypeScript.
> 1. Set Up the Frontend
> Create the frontend application inside the `frontend/` directory using React, Vite, and TypeScript.
> Connect the application to the existing FastAPI backend at:
> `http://localhost:8000`
> Make sure the backend allows requests from the Vite development server, typically:
> `http://localhost:5173`
> Use the existing API endpoints from Problem 7 rather than creating mock data or duplicating backend business logic.
> 2. Build the Ticket Management Interface
> Create a dashboard that displays all three tickets (101, 102, and 103).
> For each ticket, show:
>
> * Ticket ID and description.
> * Current status, such as Open, Running, or Resolved.
> * Relevant business details.
> * A clear action to select and start processing the ticket.
>
> Users should be able to select one ticket and trigger the corresponding multi-agent workflow through the backend API.
> When the workflow finishes successfully, update the ticket status to Resolved based on the backend response.
> 3. Display Agent Activities
> Create a live activity panel showing what the AI agents are doing while processing a ticket.
> The dashboard should display:
>
> * Which agent is currently working.
> * Messages, findings, and decisions from each agent.
> * Delegations between agents.
> * MCP tools used during execution.
> * Progress updates and execution results.
>
> Use the backend agent-events endpoint to refresh the activity feed while a ticket is running.
> Make it easy to distinguish the five agents: Boss, Inventory, Accounting, Facilities, and Customer Service.
> 4. Show Agent Contributions
> After a ticket finishes processing, display a concise summary of what each participating agent accomplished.
> Include:
>
> * The agent's role in resolving the ticket.
> * Key actions performed.
> * Important findings or recommendations.
> * Tools used, where relevant.
>
> Only display agents that actually participated in the workflow.
> 5. Add Human Approval Controls
> Create a dedicated area for pending payment or purchase approvals.
> When an agent prepares a financial request, the dashboard should display:
>
> * The transaction purpose.
> * Payment amount.
> * Related ticket.
> * Relevant vendor or recipient.
> * Current approval status.
>
> Allow the human operator to review and approve the request.
> The approval button should call the existing backend approval endpoint. Agents must not execute payments independently.
> Make sure the UI clearly shows whether a payment is pending, approved, rejected, or completed.
> 6. Display the Checking Account Balance
> Add a prominent cash balance display using the backend cash-balance API.
> The displayed amount should reflect the current checking account balance from the database.
> After a payment is approved and successfully executed, automatically refresh the balance so users can see the cash decrease.
> Do not update the balance using hardcoded values or frontend calculations.
> 7. Design a Professional Dashboard
> I want the interface to feel like a modern operations command center rather than a basic homework application.
> Please use a clean, professional design with thoughtful spacing, typography, and visual hierarchy.
> Suggested layout:
>
> * Top Header: Campus Customs branding, system status, and current cash balance.
> * Left Panel: Ticket list with status indicators and controls to start workflows.
> * Center Panel: Live agent activity feed showing collaboration and task progress.
> * Right Panel: Agent information, ticket summaries, and pending approvals.
>
> Use distinct visual identities for each agent so users can quickly recognize who is speaking or taking action.
> Make resolved tickets visually different from open tickets.
> Highlight pending approvals clearly without overwhelming the interface.
> Use subtle animations, status transitions, and responsive layouts to make the dashboard engaging and intuitive.
> The final result should look like a tool that real business operators would enjoy using every day.
> 8. Handle Loading and Error States
> Make sure the frontend handles:
>
> * Backend connection failures.
> * Ticket execution in progress.
> * Failed agent runs.
> * Empty activity feeds.
> * Missing or invalid ticket information.
> * Payment approval errors.
> * Insufficient cash balances.
>
> Disable duplicate submission buttons while requests are being processed.
> Display clear feedback when an operation succeeds or fails.
> 9. Run and Test the Dashboard
> The frontend should start from the `frontend/` directory using:
> `npm run dev`
> Verify that:
>
> * The application loads successfully in the browser.
> * All three tickets appear.
> * A user can select and start a ticket.
> * Agent activities refresh while the workflow runs.
> * Ticket statuses update correctly.
> * Agent summaries appear after execution.
> * Payment approval buttons call the backend.
> * The cash balance updates after successful payments.
> * The frontend communicates successfully with `http://localhost:8000`.
>
> Use actual backend responses rather than simulated data.
> 10. Document the Design Decisions
> Create a Markdown file at:
> `output/design.md`
> Explain the dashboard design, including:
>
> * Overall layout and navigation.
> * Visual differences between the five agents.
> * How ticket statuses are displayed.
> * How resolved tickets are distinguished from open tickets.
> * How payment approvals and cash balances are presented.
> * Color choices, typography, spacing, and interaction design.
> * Creative features that make the dashboard feel polished and useful.
>
> For each major design choice, briefly explain why it improves usability.
> 11. Update the AI Prompt Log
> Add this request to `AI_prompts.md` under:
> Problem 8: Agent Dashboard
> Include any follow-up prompts used to improve the frontend, along with a short explanation of what was missing from the initial implementation.
> 12. Final Validation
> Before finishing, confirm that:
>
> * The frontend uses React, Vite, and TypeScript.
> * All three tickets are visible.
> * Users can select and run individual tickets.
> * Agent activities are displayed and refreshed.
> * Each participating agent's contribution is summarized.
> * Ticket statuses update after successful execution.
> * Human approval is required for payments and purchases.
> * The checking balance reflects actual database values.
> * The interface is responsive and visually polished.
> * `output/design.md` documents the design decisions.
>
> For now, focus only on Problem 8. Do not implement unrelated features from later problems.
> Please summarize the frontend components created, API integrations completed, design decisions made, and any issues identified during testing .this is problem 8 Agent Dashboard

---

## Problem 9: Resolve the Tickets

### Initial prompt

> I'm ready to run the complete Campus Customs multi-agent system and resolve the three open tickets using the MCP server, FastAPI backend, and React dashboard developed in the previous problems.
> Please help me execute the full workflow, verify the results, and document what actually happened.
>
> 1. Reset the Working Database
>
> Before starting the full run, restore `data/campus_customs_new.db` using the original `data/campus_customs.db`.
> Keep the original database unchanged.
> After resetting:
>
> * Confirm that tickets 101, 102, and 103 are back to their initial states.
> * Retrieve the starting checking account balance from the `cash_accounts` table.
> * Record this balance for later financial reconciliation.
> * Verify that the working database is ready for a clean run.
>
> 2. Execute All Three Tickets
>
> Use the existing multi-agent system and dashboard to process tickets 101, 102, and 103.
> Run each ticket through the actual backend and MCP tools, allowing the Boss Agent to coordinate with the appropriate specialists.
> For each ticket:
>
> * Start the workflow through the dashboard.
> * Allow the agents to investigate the issue and delegate tasks as needed.
> * Record which agents participated and what each contributed.
> * Capture the MCP tools used during execution.
> * Process any required human approval requests.
> * Continue until the ticket reaches a valid final resolution.
>
> Do not simulate agent activities, fabricate tool responses, or manually mark tickets as resolved without completing the required workflow.
> All financial transactions must follow the existing approval and cash balance rules.
>
> 3. Compare Expected and Actual Agent Behavior
>
> Open the existing file:
> `output/desk_tickets.html`
> For each ticket tab (101, 102, and 103), complete the previously empty Actual section using the real execution results.
> Include:
>
> * Which agent the Boss contacted first.
> * Which agents actually participated.
> * The sequence of delegations between agents.
> * Which MCP tools were called.
> * Important decisions and actions.
> * The final ticket outcome.
>
> Keep the original Expected sections unchanged so I can compare my initial predictions with the actual workflow.
>
> 4. Reconcile the Cash Balance
>
> Update the Cash tab in `output/desk_tickets.html` with a detailed financial reconciliation.
> Include:
>
> Starting Balance
>
> * The checking account balance immediately after resetting the database.
>
> Cash Changes by Ticket
>
> For each of the three tickets, record:
>
> * The payment or purchase involved.
> * The reason for the transaction.
> * The amount paid.
> * Whether human approval was obtained.
> * The resulting change in checking balance.
>
> If a ticket does not require a cash payment, explicitly record a cash change of zero.
>
> Ending Balance
>
> * Calculate the final checking balance after all three tickets have been processed.
> * Retrieve the actual ending balance from the working database.
> * Verify that the calculated and database balances match exactly.
>
> Use the following reconciliation:
> Ending Cash = Starting Cash − Total Approved Payments
> Do not assume incoming revenue or additional cash.
> If there is a discrepancy, investigate and correct the underlying transaction records before finalizing the report.
>
> 5. Export the Resolved Ticket Results
>
> Create:
> `output/resolved_tickets.json`
> For each ticket, include:
>
> * Ticket ID.
> * Final status.
> * Short description of the resolution.
> * Agents involved and their individual contributions.
> * Delegations and important MCP tool actions.
> * Any required human approvals.
> * Related payments or purchases, if applicable.
>
> Make sure all information reflects the actual execution results.
>
> 6. Capture the Final Dashboard
>
> Create a standalone HTML report at:
> `output/resolved_board.html`
> The report should include actual screenshots of the React dashboard showing each of the three resolved tickets.
> Requirements:
>
> * Include one screenshot for ticket 101.
> * Include one screenshot for ticket 102.
> * Include one screenshot for ticket 103.
> * Make the HTML file viewable directly in a browser.
> * Clearly identify which screenshot belongs to each ticket.
> * Ensure the screenshots reflect the real dashboard after the tickets have been resolved.
>
> Do not substitute mockups or simulated screenshots for actual dashboard captures.
>
> 7. Preserve the Audit Trail
>
> Continue appending real execution events to:
> `output/audit_trail.json`
> Include relevant agent actions, delegations, MCP tool calls, decisions, approval events, and final outcomes.
> Do not overwrite existing audit history.
> The audit trail should provide enough detail to reconstruct what happened during each ticket's execution.
>
> 8. Complete the Project Documentation
>
> Finalize `output/harness.md` so it provides a complete technical overview of the application.
> Make sure it covers:
>
> * Database tables and their purposes.
> * All MCP tools and the tables they access.
> * The five AI agents and their responsibilities.
> * Agent delegation and collaboration.
> * FastAPI endpoints and their functions.
> * React dashboard features.
> * Human approval and payment safety rules.
> * Cash balance protection.
> * Audit logging and token usage safeguards.
>
> Keep the documentation consistent with the actual implementation.
>
> 9. Update the AI Prompt Log
>
> Add this request to `AI_prompts.md` under:
> Problem 9: Resolve the Tickets
> Record any follow-up prompts used to fix execution issues, reconcile financial discrepancies, or improve the final deliverables.
>
> 10. Final Verification
>
> Before finishing, confirm that:
>
> * The working database was reset before the full run.
> * All three tickets were processed using the actual agent system.
> * Tickets 101, 102, and 103 reached valid resolved states.
> * The Actual sections reflect real agent activities.
> * The Expected sections remain unchanged.
> * Every payment received explicit human approval.
> * The cash reconciliation matches the `cash_accounts` table.
> * `output/resolved_tickets.json` contains verified results.
> * `output/resolved_board.html` contains three actual dashboard screenshots.
> * `output/audit_trail.json` preserves the execution history.
> * `output/harness.md` documents the complete system.
>
> If any ticket cannot be resolved, or if an approval, database update, or screenshot capture cannot be completed, report the issue accurately rather than inventing a successful result.
> Please summarize the execution results for all three tickets, the starting and ending checking balances, the payments made, and the final files created or updated.

---

## Problem 10: Reflection

### Initial prompt

> I want to complete Problem 10 by writing a detailed reflection on the Campus Customs multi-agent system we developed and tested in the previous problems.
> Please review the actual execution results of tickets 101, 102, and 103, evaluate how the agents performed, and help me complete the Reflection tab in `output/desk_tickets.html`.
> The reflection should be specific to our application, written in clear and natural English, and supported by evidence from the actual ticket executions.
>
> 1. Review the Existing Results
>
> Before writing the reflection, examine the relevant project files, including:
>
> * `output/desk_tickets.html` — the Expected and Actual sections for all three tickets, along with the Cash tab.
> * `output/resolved_tickets.json` — the final ticket outcomes and agent contributions.
> * `output/audit_trail.json` — the actual agent interactions, delegations, and MCP tool calls.
> * `output/harness.md` — the system architecture, agent responsibilities, and available tools.
> * `data/campus_customs_new.db` — the final database records and financial information.
>
> Use these files as the primary evidence for the reflection. Do not invent agent behavior, ticket outcomes, tool capabilities, or financial transactions.
>
> 2. Evaluate Agent Performance on Each Ticket
>
> For tickets 101, 102, and 103, provide a separate evaluation of how effectively the agents handled the problem.
> Discuss:
>
> * Which agents participated and what each contributed.
> * Whether the Boss Agent delegated tasks to the appropriate specialists.
> * How effectively the specialists collaborated.
> * Whether the agents used the correct MCP tools.
> * Whether the ticket was resolved successfully.
> * Any unnecessary steps, delays, repeated tool calls, or coordination issues.
> * Whether the workflow followed the required approval and safety rules.
>
> Explain why the team performed well or poorly using concrete examples from each ticket.
>
> 3. Compare Expected vs. Actual Results
>
> For each ticket, compare the original Expected plan from Problem 6 with the Actual execution recorded in Problem 9.
> Address:
>
> * Which agent I expected the Boss to contact first versus who was actually contacted.
> * The planned delegation sequence versus the real sequence.
> * The MCP tools I expected to be used versus the tools actually called.
> * Any unexpected agent interactions or additional steps.
> * Whether the final outcome matched my original expectations.
>
> Explain the most important differences and what they reveal about multi-agent coordination.
> Preserve the original Expected and Actual sections without modifying their content.
>
> 4. Evaluate Whether a Single Agent Would Be Simpler
>
> Reflect on which parts of the Campus Customs workflow could have been handled more efficiently by one AI agent with access to all the necessary MCP tools.
> Consider:
>
> * Straightforward database lookups.
> * Simple inventory or accounting checks.
> * Routine ticket status updates.
> * Tasks that do not require collaboration between departments.
>
> Explain why a single agent might be more efficient in these situations, considering fewer handoffs, lower latency, reduced token consumption, and simpler debugging.
> Also discuss which tasks benefited from multiple specialized agents, particularly when inventory, accounting, facilities, and customer service responsibilities overlapped.
> Use examples from our actual ticket executions.
>
> 5. Identify Three Additional Problems the Current System Could Solve
>
> Propose three realistic new problems that Campus Customs might encounter that could be handled using the agents and MCP tools already implemented.
> For each scenario:
>
> * Describe the business problem.
> * Identify the agents that would participate.
> * Explain which existing MCP tools they would use.
> * Describe the expected workflow and outcome.
> * Explain why the current system has sufficient capabilities to handle it.
>
> Choose examples that fit the existing database structure and implemented tool functionality.
> Do not assume capabilities that have not actually been developed.
>
> 6. Identify Three Problems That Require New Capabilities
>
> Describe three additional business problems that the current Campus Customs system would not be able to resolve with its existing agents and tools.
> For each scenario:
>
> * Explain the business problem.
> * Identify the specific limitations of the current system.
> * Describe the additional MCP tools or external integrations needed.
> * Explain whether a new specialized agent would be necessary.
> * Describe how the expanded system would handle the problem.
>
> Focus on realistic business needs such as external supplier coordination, demand forecasting, or customer communication, but only use these examples if they represent genuine gaps in our implementation.
> Clearly distinguish between what the current system can already do and what would require further development.
>
> 7. Reflect on the Overall System Design
>
> Conclude with a thoughtful assessment of the Campus Customs application.
> Discuss:
>
> * The strengths and weaknesses of the five-agent architecture.
> * The value of using MCP as a shared interface to business data.
> * The trade-offs between specialization and coordination overhead.
> * The importance of human approval for financial transactions.
> * How the audit trail improves transparency and accountability.
> * What I would improve if I continued developing the application.
>
> Connect these observations to what actually happened during the three ticket executions rather than providing a generic discussion of AI agents.
>
> 8. Update the Reflection Tab
>
> Write the complete reflection into the existing Reflection tab of:
> `output/desk_tickets.html`
> Requirements:
>
> * Keep all existing ticket tabs and the Cash tab intact.
> * Organize the reflection into clearly labeled sections.
> * Use readable paragraphs and a professional layout.
> * Include detailed explanations rather than brief generic statements.
> * Reference tickets 101, 102, and 103 wherever relevant.
> * Use actual evidence from the application and its execution logs.
> * Write in natural, first-person English that reflects my own analysis and observations.
>
> 9. Update the Prompt Log
>
> Add this request to `AI_prompts.md` under:
> Problem 10: Reflection
> Record any additional follow-up prompts used to improve the reflection.
>
> 10. Final Verification
>
> Before finishing, confirm that:
>
> * The Reflection tab is fully populated.
> * All required reflection questions are answered.
> * Each ticket receives an individual performance evaluation.
> * Expected and Actual results are compared separately for all three tickets.
> * The single-agent versus multi-agent discussion includes specific examples.
> * Three additional problems solvable with existing tools are described.
> * Three problems requiring new capabilities are described, including the necessary tools and agents.
> * The reflection is supported by real execution records.
> * The original ticket and Cash tabs remain unchanged.
> * No unsupported claims or fabricated execution results are included.
>
> Please provide a brief summary of the completed reflection and identify any missing evidence or unresolved issues that prevent a fully supported evaluation.

### Follow-up prompt

**What was missing:** The reflection identified defects in the system but nothing had been fixed:
- customer drafts leaked internal terms and used a shortened product name (101);
- a draft promised a delivery date for a restock that was never ordered (103);
- Facilities made redundant lookups (102);
- drafts went stale after approvals;
- token use was only known per ticket;
- `verify_mcp_smoke.py` failed once later problems changed the working DB;
- the frontend had 10 lint warnings.

The follow-up fixed these. Key changes: a rule check in the draft MCP tool, prompt and allowlist changes, `needs_review` flags on drafts, per-delegation token usage, a corrected smoke verifier, and a lint-clean frontend. The fixes were verified with 27/27 rule tests and a live re-run on a scratch database, which kept the Problem 9 records untouched. Details are in `output/harness.md` section 13.

> fix all the bugs

---

## Problem 11: Submit to GitHub

### Initial prompt

> I want to finalize my Campus Customs multi-agent application and prepare the entire project for submission through a public GitHub repository.
> Please review the existing project, organize the required files, verify that everything needed to run the application is included, and help me publish it to GitHub.
>
> 1. Review the Project Structure
>
> First, inspect my current project and compare it against the expected submission structure.
> The project should contain the following files and folders:
>
> ```text
> hw5/
> ├── AI_prompts.md
> ├── requirements.txt
> ├── .env.example
> ├── .gitignore
> ├── .mcp.json
> ├── README.md
> ├── data/
> │   ├── campus_customs.db
> │   └── campus_customs_new.db
> ├── mcp_server/
> │   ├── server.py
> │   └── README.md
> ├── frontend/
> ├── backend/
> │   ├── main.py
> │   ├── models.py
> │   └── prompts/
> │       ├── boss.md
> │       ├── inventory.md
> │       ├── accounting.md
> │       ├── facilities.md
> │       └── customer_service.md
> └── output/
>     ├── harness.md
>     ├── mcp_smoke.json
>     ├── desk_tickets.html
>     ├── design.md
>     ├── resolved_tickets.json
>     ├── resolved_board.html
>     ├── audit_trail.json
>     └── github_url.txt
> ```
>
> Check whether each required file exists and contains the expected content. If any files are missing, identify them and create them where appropriate using information from the existing project.
> Preserve all working code, database records, ticket results, and agent execution logs.
>
> 2. Prepare the Project for GitHub
>
> Make sure the repository is safe to publish publicly.
>
> * Do not upload my actual `.env` file.
> * Create or update `.gitignore` to exclude secrets, API keys, local virtual environments, caches, and unnecessary generated files.
> * Create `.env.example` showing the environment variables needed to run the project, including `PORTKEY_API_KEY`, without exposing real credentials.
> * Review the MCP configuration and source files for any hardcoded secrets or sensitive local paths.
> * Make sure the Python dependencies are documented in `requirements.txt`.
> * Preserve the frontend dependency files needed to install and run the React application.
>
> Importantly, both database files must be included in the repository:
>
> * `data/campus_customs.db` — the original database.
> * `data/campus_customs_new.db` — the working database.
>
> Do not accidentally exclude these database files through `.gitignore`.
>
> 3. Write a Complete README
>
> Create or improve the root `README.md` so that someone unfamiliar with my project can clone the repository and run the application.
> The README should explain:
>
> Project Overview
>
> * What the Campus Customs application does.
> * How the five-agent team works together.
> * How the MCP server connects agents to the SQLite database.
> * How the FastAPI backend and React dashboard interact.
>
> Installation
>
> * How to clone the repository.
> * How to install Python dependencies.
> * How to install frontend dependencies.
> * How to configure the environment variables using `.env.example`.
>
> Database Setup
>
> * How to copy `data/campus_customs.db` to `data/campus_customs_new.db` when a clean working database is needed.
> * How to reset the working database before running all three tickets again.
> * How to confirm the database is ready.
>
> Running the Application
>
> * How to start the MCP server.
> * How to launch the FastAPI backend.
> * How to start the React frontend.
> * Which local URLs to open.
>
> Testing the Application
>
> * How to access tickets 101, 102, and 103.
> * How to execute the agent team for each ticket.
> * How to inspect agent activity and MCP tool calls.
> * How human approval works for payments or purchases.
> * How to verify changes to the checking account balance.
> * How to reset the database for another test.
>
> Make sure every command matches the actual project implementation.
>
> 4. Verify the Submission Files
>
> Review the deliverables from Problems 1–10 and confirm they are present.
> Pay particular attention to:
>
> * `AI_prompts.md` — the prompts used throughout the assignment.
> * `output/harness.md` — database tables, MCP tools, agents, API routes, and safety rules.
> * `output/mcp_smoke.json` — MCP tool testing evidence.
> * `output/desk_tickets.html` — Expected, Actual, Cash, and Reflection sections.
> * `output/design.md` — dashboard design decisions.
> * `output/resolved_tickets.json` — results for tickets 101, 102, and 103.
> * `output/resolved_board.html` — screenshots of the resolved tickets.
> * `output/audit_trail.json` — actual agent execution history.
>
> Do not fabricate missing execution results or test evidence. If any required deliverables are incomplete, explain what still needs to be done.
>
> 5. Validate the Application
>
> Before publishing, check that:
>
> * The Python source files have no obvious syntax errors.
> * The MCP server configuration references the correct project paths.
> * The backend can access the working SQLite database.
> * The FastAPI routes are correctly configured.
> * The React frontend has the necessary dependencies and configuration.
> * The frontend can communicate with the backend.
> * All three tickets and their results are represented in the output files.
> * No API keys or other secrets are exposed.
>
> Run available validation commands where possible and report any failures accurately.
>
> 6. Publish to GitHub
>
> After the project has been reviewed and prepared, help me publish it to a public GitHub repository.
> If GitHub access is available:
>
> 1. Check the current Git repository and remote configuration.
> 2. Create a public repository if one does not already exist.
> 3. Stage the required project files.
> 4. Confirm that `.env` and all real credentials are excluded.
> 5. Commit the completed assignment.
> 6. Push the project to GitHub.
> 7. Verify that the repository is publicly accessible and contains the expected files.
>
> Do not overwrite an unrelated repository or replace existing remote history without asking me first.
> If GitHub authentication is required or direct publishing is unavailable, provide the exact commands I need to complete the upload manually.
>
> 7. Save the GitHub Repository URL
>
> Once the repository has been successfully published, create or update:
> `output/github_url.txt`
> This file should contain the public GitHub repository URL.
> Make sure the URL points to the correct repository and that graders can access it without signing in.
> Do not insert a placeholder URL and claim the repository was published.
>
> 8. Final Submission Check
>
> Perform one final review and confirm:
>
> * The GitHub repository is public.
> * All required source code and output files are included.
> * Both SQLite database files are present.
> * The actual `.env` file is excluded.
> * `.env.example` contains no real secrets.
> * The README provides complete setup and execution instructions.
> * The five agent prompts are included.
> * The MCP server, backend, and frontend code are present.
> * The required ticket results, audit trail, and reflection are included.
> * `output/github_url.txt` contains the verified repository URL.
>
> Finally, provide the repository link and a concise summary of the submission status, including any outstanding issues.
> Also remind me to submit the same GitHub repository URL through Canvas, since that is the final submission requirement.

---

## Entry template

Copy this block when starting a new problem. Fill it in only with prompts that were actually given.

```markdown
## Problem [number]: [title]

### Initial prompt

> [Exact prompt]

### Follow-up prompt

**What was missing:** [Short explanation]

> [Exact follow-up prompt]
```
