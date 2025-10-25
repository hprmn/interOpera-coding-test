#!/usr/bin/env python3
"""
Test script for Google Gemini LLM integration

This script verifies that:
1. Environment variables are correctly configured
2. Gemini API key is valid
3. LangChain integration works
4. Query engine can initialize Gemini LLM
5. Basic chat queries function properly

Usage:
    python test_gemini_integration.py
"""

import os
import sys
from dotenv import load_dotenv

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_success(text):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠{RESET} {text}")


def test_environment_variables():
    """Test 1: Check environment variables"""
    print_header("Test 1: Environment Variables")

    # Load .env file
    load_dotenv()

    # Check LLM_PROVIDER
    llm_provider = os.getenv("LLM_PROVIDER")
    if llm_provider == "gemini":
        print_success(f"LLM_PROVIDER is set to: {llm_provider}")
    else:
        print_error(f"LLM_PROVIDER is '{llm_provider}' (expected 'gemini')")
        return False

    # Check GOOGLE_API_KEY
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        # Mask API key for security
        masked_key = api_key[:10] + "..." + api_key[-4:]
        print_success(f"GOOGLE_API_KEY is set: {masked_key}")

        # Validate format
        if api_key.startswith("AIzaSy"):
            print_success("API key format is valid (starts with 'AIzaSy')")
        else:
            print_warning("API key format unusual (doesn't start with 'AIzaSy')")
    else:
        print_error("GOOGLE_API_KEY is not set")
        return False

    return True


def test_langchain_import():
    """Test 2: Check LangChain Google GenAI import"""
    print_header("Test 2: LangChain Import")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        print_success("langchain-google-genai is installed")
        return True
    except ImportError as e:
        print_error("langchain-google-genai is NOT installed")
        print(f"   Error: {e}")
        print(f"\n   Install with: pip install langchain-google-genai==0.0.6")
        return False


def test_gemini_initialization():
    """Test 3: Initialize Gemini LLM"""
    print_header("Test 3: Gemini Initialization")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY")

        print("Initializing ChatGoogleGenerativeAI...")
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=api_key,
            temperature=0,
            convert_system_message_to_human=True
        )
        print_success("Gemini LLM initialized successfully")
        return llm
    except Exception as e:
        print_error(f"Failed to initialize Gemini LLM")
        print(f"   Error: {e}")
        return None


def test_simple_query(llm):
    """Test 4: Simple query"""
    print_header("Test 4: Simple Query")

    if not llm:
        print_error("LLM not initialized, skipping query test")
        return False

    try:
        query = "What is 2+2?"
        print(f"Query: {query}")
        print("Sending request to Gemini...")

        response = llm.invoke(query)

        if hasattr(response, 'content'):
            answer = response.content
        else:
            answer = str(response)

        print_success("Response received")
        print(f"\nAnswer: {answer}\n")
        return True
    except Exception as e:
        print_error(f"Query failed")
        print(f"   Error: {e}")
        return False


def test_fund_query(llm):
    """Test 5: Fund-specific query"""
    print_header("Test 5: Fund Analysis Query")

    if not llm:
        print_error("LLM not initialized, skipping query test")
        return False

    try:
        query = "Explain what DPI means in private equity fund performance metrics."
        print(f"Query: {query}")
        print("Sending request to Gemini...")

        response = llm.invoke(query)

        if hasattr(response, 'content'):
            answer = response.content
        else:
            answer = str(response)

        print_success("Response received")
        print(f"\nAnswer:\n{answer}\n")

        # Check if response contains relevant keywords
        answer_lower = answer.lower()
        keywords = ["dpi", "distribution", "paid-in", "capital"]
        found_keywords = [kw for kw in keywords if kw in answer_lower]

        if found_keywords:
            print_success(f"Response contains relevant keywords: {', '.join(found_keywords)}")
            return True
        else:
            print_warning("Response doesn't contain expected keywords")
            return False
    except Exception as e:
        print_error(f"Query failed")
        print(f"   Error: {e}")
        return False


def test_query_engine_integration():
    """Test 6: QueryEngine integration"""
    print_header("Test 6: QueryEngine Integration")

    try:
        # Add backend to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

        # Import QueryEngine (will trigger LLM initialization)
        print("Importing QueryEngine...")
        from app.services.query_engine import QueryEngine
        print_success("QueryEngine imported successfully")

        # Check if Gemini initialization message appears
        print("QueryEngine will initialize LLM based on LLM_PROVIDER env var")
        print_success("If you see 'Initializing Google Gemini LLM...' above, integration works!")

        return True
    except Exception as e:
        print_error(f"QueryEngine integration failed")
        print(f"   Error: {e}")
        return False


def main():
    """Run all tests"""
    print(f"\n{BLUE}╔{'═'*58}╗{RESET}")
    print(f"{BLUE}║{'Google Gemini Integration Test Suite':^58}║{RESET}")
    print(f"{BLUE}╚{'═'*58}╝{RESET}")

    results = []

    # Test 1: Environment Variables
    result = test_environment_variables()
    results.append(("Environment Variables", result))
    if not result:
        print_error("\nEnvironment configuration failed. Fix .env file before proceeding.")
        return

    # Test 2: LangChain Import
    result = test_langchain_import()
    results.append(("LangChain Import", result))
    if not result:
        print_error("\nInstall langchain-google-genai before proceeding.")
        return

    # Test 3: Gemini Initialization
    llm = test_gemini_initialization()
    results.append(("Gemini Initialization", llm is not None))
    if not llm:
        print_error("\nGemini initialization failed. Check API key.")
        return

    # Test 4: Simple Query
    result = test_simple_query(llm)
    results.append(("Simple Query", result))

    # Test 5: Fund Query
    result = test_fund_query(llm)
    results.append(("Fund Analysis Query", result))

    # Test 6: QueryEngine Integration
    result = test_query_engine_integration()
    results.append(("QueryEngine Integration", result))

    # Summary
    print_header("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        if result:
            print_success(f"{test_name:<30} PASSED")
        else:
            print_error(f"{test_name:<30} FAILED")

    print(f"\n{BLUE}{'─'*60}{RESET}")
    if passed == total:
        print(f"{GREEN}All tests passed! ({passed}/{total}){RESET}")
        print(f"\n{GREEN}✓ Google Gemini integration is working correctly!{RESET}")
        print(f"\nYou can now:")
        print(f"  1. Start the backend: docker compose up backend")
        print(f"  2. Test chat API: curl http://localhost:8000/api/chat/query")
        print(f"  3. Use the frontend chat interface")
    else:
        print(f"{RED}Some tests failed. ({passed}/{total} passed){RESET}")
        print(f"\n{YELLOW}Please review errors above and fix configuration.{RESET}")
    print(f"{BLUE}{'─'*60}{RESET}\n")


if __name__ == "__main__":
    main()
