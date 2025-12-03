# Testing Scenarios for Live Demo

This document contains testing scenarios for demonstrating the Multi-Agent Customer Support System. Each feature has 2 test cases designed to showcase functionality during live demos.

---

## Feature 1: User Authentication

### Test 1.1: Email/Password Registration and Login
**Objective:** Verify user can create account and login with credentials

**Steps:**
1. Navigate to the login screen
2. Click "Sign Up"
3. Enter email: `demo@example.com`
4. Enter password: `DemoPass123!`
5. Click "Create Account"
6. Verify successful account creation
7. Logout
8. Login with same credentials
9. Verify successful authentication

**Expected Result:** User successfully registers, logs out, and logs back in

---

### Test 1.2: Guest Access
**Objective:** Verify guest users can access the system without authentication

**Steps:**
1. Navigate to the login screen
2. Click "Continue as Guest"
3. Verify chat interface loads
4. Send message: "Hello, I need help"
5. Verify agent responds

**Expected Result:** Guest user can access system and interact with agents without account creation

---

## Feature 2: RAG Semantic Search (Product Search)

### Test 2.1: Semantic Product Search with Price Filter
**Objective:** Verify RAG semantic search finds relevant products using vector embeddings

**Steps:**
1. Login to the system
2. Send message: "I'm looking for a gaming computer under $1500"
3. Wait for agent response
4. Verify results include gaming-related products
5. Verify all results are under $1500

**Expected Result:** Agent uses semantic search to find gaming laptops/desktops within budget, demonstrating vector embedding matches

---

### Test 2.2: Category-Based Semantic Search
**Objective:** Verify semantic search works with natural language queries

**Steps:**
1. Send message: "Show me smartphones with good cameras"
2. Wait for agent response
3. Verify results include phones/smartphones
4. Verify product descriptions mention camera features

**Expected Result:** Agent understands natural language intent and returns relevant smartphone products

---

## Feature 3: Product Information Retrieval

### Test 3.1: Comprehensive Product Info (Smart Wrapper)
**Objective:** Verify get_product_info returns details + inventory + reviews

**Steps:**
1. Send message: "Tell me about product PROD-001"
2. Wait for agent response
3. Verify response includes:
   - Product name and description
   - Price
   - Stock/inventory level
   - Customer reviews and ratings

**Expected Result:** Agent returns comprehensive product information in single response

---

### Test 3.2: Multiple Product Details After Search
**Objective:** Verify efficient multi-product fetch using get_all_saved_products_info

**Steps:**
1. Send message: "Search for laptops"
2. Wait for search results (should show 3-5 products)
3. Send follow-up: "Show me details on all of them"
4. Verify response includes details for all products from search

**Expected Result:** Agent retrieves all product details in single efficient call (no iterative loops)

---

## Feature 4: Order Tracking

### Test 4.1: Track Specific Order
**Objective:** Verify order tracking by order ID

**Steps:**
1. Send message: "Track my order ORD-12345"
2. Wait for agent response
3. Verify response includes:
   - Order ID
   - Order status (e.g., "Shipped", "Delivered")
   - Tracking information

**Expected Result:** Agent successfully retrieves and displays order status

---

### Test 4.2: View Order History
**Objective:** Verify user can view complete order history

**Steps:**
1. Send message: "Show me my order history"
2. Wait for agent response
3. Verify response includes multiple orders
4. Verify each order shows:
   - Order ID
   - Order date
   - Total amount
   - Status

**Expected Result:** Agent displays comprehensive order history for the user

---

## Feature 5: Billing and Invoices

### Test 5.1: Get Invoice by Order ID
**Objective:** Verify invoice retrieval for specific order

**Steps:**
1. Send message: "Get the invoice for order ORD-12345"
2. Wait for agent response
3. Verify response includes:
   - Invoice number
   - Order ID
   - Line items with prices
   - Total amount
   - Payment method

**Expected Result:** Agent retrieves and displays complete invoice details

---

### Test 5.2: Check Payment Status
**Objective:** Verify payment status verification

**Steps:**
1. Send message: "Check payment status for order ORD-12345"
2. Wait for agent response
3. Verify response includes:
   - Payment status (e.g., "Paid", "Pending")
   - Payment date (if paid)
   - Payment method

**Expected Result:** Agent displays accurate payment status information

---

## Feature 6: Refund Processing (Sequential Workflow)

### Test 6.1: Successful Refund Request
**Objective:** Verify SequentialAgent processes refund with step-by-step validation

**Steps:**
1. Send message: "I want a refund for order ORD-12345"
2. Wait for agent response
3. Observe sequential workflow:
   - Step 1: Order validation ✓
   - Step 2: Eligibility check ✓
   - Step 3: Refund processing ✓
4. Verify success message

**Expected Result:** Agent processes refund through validated sequential workflow pattern

---

### Test 6.2: Refund Request - Ineligible Order
**Objective:** Verify refund workflow handles validation failures

**Steps:**
1. Send message: "I want a refund for order ORD-99999" (non-existent order)
2. Wait for agent response
3. Verify workflow stops at validation step
4. Verify error message explains why refund cannot be processed

**Expected Result:** Sequential workflow validates order and gracefully handles failure

---

## Feature 7: Multi-Session Conversations

### Test 7.1: Create New Chat Session
**Objective:** Verify users can create multiple conversation threads

**Steps:**
1. In current session, send: "I need help with my order"
2. Wait for response
3. Click "New Chat" or create new session
4. Verify new empty chat interface appears
5. Send different message: "Show me laptops"
6. Verify this is separate conversation

**Expected Result:** User can maintain multiple independent chat sessions

---

### Test 7.2: Switch Between Sessions
**Objective:** Verify context is maintained when switching sessions

**Steps:**
1. In Session A, send: "I'm looking at order ORD-12345"
2. Create Session B, send: "Show me gaming laptops"
3. Switch back to Session A
4. Verify previous messages about ORD-12345 are still visible
5. Send follow-up: "What's the status?"
6. Verify agent maintains context from Session A

**Expected Result:** Each session maintains independent conversation context

---

## Feature 8: Memory Bank (Cross-Session Memory)

### Test 8.1: User Preference Memory
**Objective:** Verify Memory Bank stores and recalls user preferences

**Steps:**
1. **Session 1:**
   - Login as user
   - Send: "I prefer products under $500"
   - Send: "I'm interested in gaming laptops"
   - Logout
2. **Session 2 (New login):**
   - Login as same user
   - Send: "Show me some laptop recommendations"
   - Verify agent mentions budget preference (~$500)
   - Verify suggestions prioritize gaming laptops

**Expected Result:** Memory Bank recalls user preferences across different sessions

---

### Test 8.2: Past Issue Memory
**Objective:** Verify Memory Bank remembers past problems

**Steps:**
1. **Session 1:**
   - Send: "I had delivery issues with order ORD-12345"
   - Wait for agent to acknowledge
   - End session
2. **Session 2 (New login):**
   - Send: "I want to place a new order"
   - Verify agent references previous delivery issue
   - Verify agent offers to help ensure smooth delivery

**Expected Result:** Agent remembers and references past issues to improve service

---

## Feature 9: Voice Features

### Test 9.1: Speech-to-Text Input
**Objective:** Verify voice input converts to text and processes query

**Steps:**
1. Click microphone/voice input button
2. Grant browser microphone permissions
3. Speak: "Show me laptops under one thousand dollars"
4. Verify text appears in input field
5. Send message
6. Verify agent processes the query correctly

**Expected Result:** Voice input successfully converts to text and processes

---

### Test 9.2: Text-to-Speech Output
**Objective:** Verify agent responses can be read aloud

**Steps:**
1. Send message: "What's the status of my order?"
2. Wait for text response
3. Click speaker/text-to-speech button on response
4. Verify browser reads response aloud
5. Verify voice pronunciation is clear

**Expected Result:** Agent response is converted to speech and played back clearly

---

## Feature 10: Multi-Agent Orchestration

### Test 10.1: Root Agent Routing to Product Agent
**Objective:** Verify Root Agent delegates to Product Agent

**Steps:**
1. Send message: "I'm looking for wireless headphones"
2. Observe in logs/UI that Root Agent routes to Product Agent
3. Verify Product Agent (Gemini 2.5 Pro) handles query
4. Verify appropriate product tools are used (search_products)

**Expected Result:** Root Agent correctly identifies product query and delegates to Product Agent

---

### Test 10.2: Root Agent Routing to Multiple Agents
**Objective:** Verify Root Agent handles complex multi-agent workflows

**Steps:**
1. Send: "I ordered a laptop last week, what's the status? Also, send me the invoice"
2. Observe Root Agent coordinates:
   - Order Agent: Retrieves order status
   - Billing Agent: Retrieves invoice
3. Verify both responses are included in single reply

**Expected Result:** Root Agent orchestrates multiple specialist agents to fulfill complex request

---

## Feature 11: Retry Logic & Error Handling

### Test 11.1: Transient Error Recovery
**Objective:** Verify exponential backoff handles temporary failures

**Steps:**
1. Simulate transient error (if possible in test environment)
2. Send message: "Show me products"
3. Observe system automatically retries with backoff
4. Verify request eventually succeeds
5. Verify user sees seamless experience

**Expected Result:** System gracefully handles transient errors with automatic retry

---

### Test 11.2: Graceful Error Messages
**Objective:** Verify user-friendly error messages for failures

**Steps:**
1. Send message requesting non-existent data: "Show order ORD-99999999"
2. Wait for response
3. Verify error message is user-friendly (not technical stack trace)
4. Verify agent offers helpful alternatives

**Expected Result:** Errors are handled gracefully with helpful user-facing messages

---

## Feature 12: Context-Aware Product Retrieval

### Test 12.1: Get Last Mentioned Product
**Objective:** Verify agent remembers recently discussed products

**Steps:**
1. Send: "Tell me about the UltraBook Pro"
2. Wait for response
3. Send follow-up: "What's the warranty on that?"
4. Verify agent understands "that" refers to UltraBook Pro
5. Verify response is contextually relevant

**Expected Result:** Agent uses get_last_mentioned_product to maintain conversation context

---

### Test 12.2: Contextual Follow-up Questions
**Objective:** Verify natural conversation flow with product context

**Steps:**
1. Send: "Show me gaming laptops"
2. Agent returns list of products
3. Send: "Tell me more about the first one"
4. Verify agent retrieves details for first product in previous results
5. Send: "Is it in stock?"
6. Verify agent checks inventory for same product

**Expected Result:** Agent maintains product context across multiple turns

---

## Demo Flow Recommendation

For a **15-minute live demo**, follow this sequence:

1. **Authentication** (1 min): Test 1.2 - Guest Access
2. **Product Search** (2 min): Test 2.1 - Semantic Search
3. **Product Info** (1.5 min): Test 3.1 - Comprehensive Info
4. **Order Tracking** (1.5 min): Test 4.1 - Track Order
5. **Refund Workflow** (2.5 min): Test 6.1 - Sequential Refund
6. **Multi-Session** (2 min): Test 7.1 - Create Sessions
7. **Memory Bank** (2.5 min): Test 8.1 - Preference Memory
8. **Multi-Agent** (2 min): Test 10.2 - Complex Routing

**Total: ~15 minutes**

---

## Test Data Reference

Use these sample IDs for testing:

**Products:**
- PROD-001: Gaming Laptop
- PROD-002: Wireless Mouse
- PROD-003: USB-C Cable

**Orders:**
- ORD-12345: Delivered order
- ORD-67890: Shipped order
- ORD-99999: Non-existent (for error testing)

**Users:**
- demo@example.com / DemoPass123!
- test@example.com / TestPass456!

**Search Terms:**
- "gaming laptop"
- "wireless headphones"
- "smartphones under $500"
- "USB cables"

---

## Notes for Presenters

- **Highlight RAG**: Emphasize semantic search understanding "gaming computer" = gaming laptop/desktop
- **Show Logs**: If possible, display console logs showing agent routing decisions
- **Memory Bank**: Best demonstrated across two separate sessions (logout/login)
- **Sequential Workflow**: Emphasize validation gates in refund processing
- **Multi-Agent**: Point out which agent (Product/Order/Billing) handles each request

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Project:** Multi-Agent Customer Support System
