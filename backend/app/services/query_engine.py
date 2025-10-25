"""
Query engine service for RAG-based question answering
"""
from typing import Dict, Any, List, Optional
import time
import os
from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from app.core.config import settings
from app.services.vector_store import VectorStore
from app.services.metrics_calculator import MetricsCalculator
from sqlalchemy.orm import Session

# Import Gemini if available
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: langchain-google-genai not installed. Install with: pip install langchain-google-genai")


class QueryEngine:
    """RAG-based query engine for fund analysis"""
    
    def __init__(self, db: Session):
        self.db = db
        self.vector_store = VectorStore()
        self.metrics_calculator = MetricsCalculator(db)
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self):
        """
        Initialize LLM based on LLM_PROVIDER environment variable

        Supported providers:
        - gemini: Google Gemini (free tier available)
        - openai: OpenAI GPT models (paid)
        - ollama: Local Ollama models (free, offline)
        """
        llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()

        # Google Gemini
        if llm_provider == "gemini":
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment variables")

            if not GEMINI_AVAILABLE:
                raise ImportError(
                    "langchain-google-genai not installed. "
                    "Install with: pip install langchain-google-genai"
                )

            print("Initializing Google Gemini LLM...")
            return ChatGoogleGenerativeAI(
                model="models/gemini-2.5-flash",  # Latest Gemini Flash model
                google_api_key=google_api_key,
                temperature=0,
                convert_system_message_to_human=True  # Gemini compatibility
            )

        # OpenAI
        elif llm_provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables")

            print("Initializing OpenAI LLM...")
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0,
                openai_api_key=settings.OPENAI_API_KEY
            )

        # Ollama (local)
        elif llm_provider == "ollama":
            ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
            ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

            print(f"Initializing Ollama LLM (model: {ollama_model})...")
            return Ollama(
                model=ollama_model,
                base_url=ollama_base_url
            )

        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: {llm_provider}. "
                f"Supported values: gemini, openai, ollama"
            )
    
    async def process_query(
        self, 
        query: str, 
        fund_id: Optional[int] = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query using RAG
        
        Args:
            query: User question
            fund_id: Optional fund ID for context
            conversation_history: Previous conversation messages
            
        Returns:
            Response with answer, sources, and metrics
        """
        start_time = time.time()
        
        # Step 1: Classify query intent
        intent = await self._classify_intent(query)
        
        # Step 2: Retrieve relevant context from vector store
        filter_metadata = {"fund_id": fund_id} if fund_id else None
        relevant_docs = await self.vector_store.similarity_search(
            query=query,
            k=settings.TOP_K_RESULTS,
            filter_metadata=filter_metadata
        )
        
        # Step 3: Calculate metrics if needed
        metrics = None
        if intent == "calculation" and fund_id:
            metrics = self.metrics_calculator.calculate_all_metrics(fund_id)
        
        # Step 4: Generate response using LLM
        answer = await self._generate_response(
            query=query,
            context=relevant_docs,
            metrics=metrics,
            conversation_history=conversation_history or []
        )
        
        processing_time = time.time() - start_time
        
        return {
            "answer": answer,
            "sources": [
                {
                    "content": doc["content"],
                    "metadata": {
                        k: v for k, v in doc.items() 
                        if k not in ["content", "score"]
                    },
                    "score": doc.get("score")
                }
                for doc in relevant_docs
            ],
            "metrics": metrics,
            "processing_time": round(processing_time, 2)
        }
    
    async def _classify_intent(self, query: str) -> str:
        """
        Classify query intent
        
        Returns:
            'calculation', 'definition', 'retrieval', or 'general'
        """
        query_lower = query.lower()
        
        # Calculation keywords
        calc_keywords = [
            "calculate", "what is the", "current", "dpi", "irr", "tvpi", 
            "rvpi", "pic", "paid-in capital", "return", "performance"
        ]
        if any(keyword in query_lower for keyword in calc_keywords):
            return "calculation"
        
        # Definition keywords
        def_keywords = [
            "what does", "mean", "define", "explain", "definition", 
            "what is a", "what are"
        ]
        if any(keyword in query_lower for keyword in def_keywords):
            return "definition"
        
        # Retrieval keywords
        ret_keywords = [
            "show me", "list", "all", "find", "search", "when", 
            "how many", "which"
        ]
        if any(keyword in query_lower for keyword in ret_keywords):
            return "retrieval"
        
        return "general"
    
    async def _generate_response(
        self,
        query: str,
        context: List[Dict[str, Any]],
        metrics: Optional[Dict[str, Any]],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Generate response using LLM"""
        
        # Build context string
        context_str = "\n\n".join([
            f"[Source {i+1}]\n{doc['content']}"
            for i, doc in enumerate(context[:3])  # Use top 3 sources
        ])
        
        # Build metrics string
        metrics_str = ""
        if metrics:
            metrics_str = "\n\nAvailable Metrics:\n"
            for key, value in metrics.items():
                if value is not None:
                    metrics_str += f"- {key.upper()}: {value}\n"
        
        # Build conversation history string
        history_str = ""
        if conversation_history:
            history_str = "\n\nPrevious Conversation:\n"
            for msg in conversation_history[-3:]:  # Last 3 messages
                history_str += f"{msg['role']}: {msg['content']}\n"
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a financial analyst assistant specializing in private equity fund performance.

Your role:
- Answer questions about fund performance using provided context
- Calculate metrics like DPI, IRR when asked
- Explain complex financial terms in simple language
- Always cite your sources from the provided documents

When calculating:
- Use the provided metrics data
- Show your work step-by-step
- Explain any assumptions made

Format your responses:
- Be concise but thorough
- Use bullet points for lists
- Bold important numbers using **number**
- Provide context for metrics"""),
            ("user", """Context from documents:
{context}
{metrics}
{history}

Question: {query}

Please provide a helpful answer based on the context and metrics provided.""")
        ])
        
        # Generate response
        messages = prompt.format_messages(
            context=context_str,
            metrics=metrics_str,
            history=history_str,
            query=query
        )
        
        try:
            response = self.llm.invoke(messages)
            if hasattr(response, 'content'):
                return response.content
            return str(response)
        except Exception as e:
            return f"I apologize, but I encountered an error generating a response: {str(e)}"
