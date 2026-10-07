"""
tests/conftest.py
=================
Shared pytest fixtures for the test suite.

Strategy:
- All tests use an in-memory SQLite database (via aiosqlite).
- The FastAPI dependency overrides replace the real DB session and
  storage provider with test doubles.
- No real PostgreSQL connection is required.
- The storage provider uses a temp directory so file I/O works without
  a real filesystem mount.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Patch environment BEFORE importing the app so settings validation passes
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("REDIS_PASSWORD", "test_redis_password")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_32chars")
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["APP_ENV"] = "development"  # Ensures DB init runs

# ---------------------------------------------------------------------------
# App imports — must come after env patching
# ---------------------------------------------------------------------------
from app.db.base import Base  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.api.deps import (  # noqa: E402
    get_db_session,
    get_storage_provider,
    get_ocr_provider,
    get_llm_provider,
)
from app.services.storage.local import LocalStorageProvider  # noqa: E402
from app.services.ocr.base import OCRProvider, OCRResult, OCRError  # noqa: E402
from app.services.llm.base import LLMProvider, LLMError  # noqa: E402
from app.agents.classification.schemas import DocumentClassification  # noqa: E402
from app.agents.extraction.schemas import (  # noqa: E402
    ContactInfo,
    ContractExtraction,
    InvoiceExtraction,
    InvoiceLineItem,
    KeyValueItem,
    OtherExtraction,
    PurchaseOrderExtraction,
    PurchaseOrderLineItem,
    ReceiptExtraction,
    ReceiptItem,
)
from app.agents.validation.schemas import (  # noqa: E402
    SemanticValidationIssue,
    SemanticValidationResult,
)
from app.services.rag.generator import GeneratedRagAnswer  # noqa: E402
from app.core.enums import DocumentType  # noqa: E402

# Ensure all models are registered with Base.metadata
import app.models  # noqa: E402, F401

# ---------------------------------------------------------------------------
# In-memory SQLite engine for tests
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    # SQLite doesn't support the same pool config as Postgres
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


from app.db.session import set_session_maker

set_session_maker(TestSessionLocal)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once for the entire test session."""
    set_session_maker(TestSessionLocal)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    set_session_maker(None)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all tables between tests to ensure isolation."""
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture(scope="session")
def tmp_storage_dir():
    """Create a temporary directory for file storage during the test session."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest_asyncio.fixture
async def db_session(clean_tables) -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session with automatic rollback."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class MockOCRProvider(OCRProvider):
    """Test double for OCRProvider that returns deterministic text without Tesseract."""

    def __init__(
        self,
        text: str = "INVOICE #INV-2026-001\nVendor: Acme Corp\nTotal: $1,250.00",
        should_fail: bool = False,
        page_count: int = 1,
        processing_time_ms: int = 42,
    ) -> None:
        self.text = text
        self.should_fail = should_fail
        self.page_count = page_count
        self.processing_time_ms = processing_time_ms
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock_ocr"

    async def extract_text(self, file_path: str, file_type: str) -> OCRResult:
        self.call_count += 1
        if self.should_fail:
            raise OCRError("Simulated OCR failure", provider=self.provider_name)
        return OCRResult(
            text=self.text,
            provider=self.provider_name,
            page_count=self.page_count,
            processing_time_ms=self.processing_time_ms,
            metadata={"confidence": 0.99, "mock": True},
        )


class FakeLLMProvider(LLMProvider):
    """Test double for LLMProvider that returns deterministic structured output."""

    def __init__(
        self,
        default_type: DocumentType = DocumentType.INVOICE,
        confidence: float = 0.95,
        reasoning: str = "Document contains invoice number and payment terms.",
        signals: list[str] | None = None,
        should_fail: bool = False,
        extraction_override: object = None,
    ) -> None:
        self.default_type = default_type
        self.confidence = confidence
        self.reasoning = reasoning
        self.signals = signals if signals is not None else ["invoice number", "line items", "total amount"]
        self.should_fail = should_fail
        self.extraction_override = extraction_override
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "fake_llm"

    async def generate_structured(
        self,
        prompt: str,
        schema: type,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ):
        self.call_count += 1
        if self.should_fail:
            raise LLMError("Simulated LLM generation error", provider=self.provider_name)
        if self.extraction_override is not None:
            return self.extraction_override
        if schema == DocumentClassification:
            return DocumentClassification(
                document_type=self.default_type,
                confidence=self.confidence,
                reasoning=self.reasoning,
                signals=self.signals,
            )
        elif schema == InvoiceExtraction:
            return InvoiceExtraction(
                invoice_number="INV-2026-001",
                invoice_date="2026-01-15",
                due_date="2026-02-15",
                currency="USD",
                vendor=ContactInfo(name="Acme Corp", address="123 Industrial Way"),
                customer=ContactInfo(name="Global Corp", address="456 Tech Blvd"),
                line_items=[
                    InvoiceLineItem(description="Consulting Services", quantity=10, unit_price=150.0, amount=1500.0)
                ],
                subtotal=1500.0,
                tax=150.0,
                total=1650.0,
                payment_terms="Net 30",
            )
        elif schema == ReceiptExtraction:
            return ReceiptExtraction(
                receipt_number="REC-999",
                transaction_date="2026-01-15 14:30",
                merchant="Coffee Shop",
                merchant_address="789 Main St",
                currency="USD",
                items=[ReceiptItem(description="Espresso", quantity=2, unit_price=4.5, amount=9.0)],
                subtotal=9.0,
                tax=0.9,
                total=9.9,
                payment_method="Visa ****1234",
            )
        elif schema == PurchaseOrderExtraction:
            return PurchaseOrderExtraction(
                po_number="PO-2026-444",
                po_date="2026-01-10",
                delivery_date="2026-01-25",
                currency="USD",
                buyer=ContactInfo(name="Enterprise Co"),
                supplier=ContactInfo(name="Supplies Direct"),
                shipping_address="Dock 3, Warehouse A",
                billing_address="Finance Dept, Suite 200",
                line_items=[
                    PurchaseOrderLineItem(description="Paper Reams", quantity=50, unit_price=10.0, amount=500.0)
                ],
                subtotal=500.0,
                tax=40.0,
                total=540.0,
                payment_terms="Net 60",
            )
        elif schema == ContractExtraction:
            return ContractExtraction(
                contract_title="Master Services Agreement",
                contract_number="MSA-2026-01",
                effective_date="2026-01-01",
                expiration_date="2027-01-01",
                parties=["Acme Corp", "Beta LLC"],
                governing_law="State of Delaware",
                jurisdiction="Delaware Chancery Court",
                payment_terms="Monthly invoicing",
                termination_terms="30 days written notice",
                key_obligations=["Provide software consulting", "Maintain confidentiality"],
                important_dates=["Annual review on Nov 1"],
            )
        elif schema == OtherExtraction:
            return OtherExtraction(
                title="Company Announcement",
                document_date="2026-01-02",
                entities=["Acme Corp"],
                key_values=[KeyValueItem(key="Quarter", value="Q1 2026")],
                summary="General announcement regarding Q1 company kickoff.",
            )
        elif schema == SemanticValidationResult:
            return SemanticValidationResult(
                issues=[],
                semantic_score=1.0,
                summary="Semantic validation passed. Data is consistent with OCR text.",
            )
        elif schema == GeneratedRagAnswer:
            return GeneratedRagAnswer(
                answer="According to the invoice, the total amount due is $1,650.00 [Source 1].",
                sources_cited=[1],
                has_sufficient_evidence=True,
            )
        return schema()


@pytest.fixture
def mock_ocr() -> MockOCRProvider:
    """Fixture providing a fresh MockOCRProvider instance."""
    return MockOCRProvider()


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    """Fixture providing a fresh FakeLLMProvider instance."""
    return FakeLLMProvider()


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession,
    tmp_storage_dir: str,
    mock_ocr: MockOCRProvider,
    fake_llm: FakeLLMProvider,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client with overridden DB session, storage, OCR, and LLM providers.

    Dependency overrides ensure:
    - db_session → in-memory SQLite session
    - get_storage_provider → LocalStorageProvider pointed at tmp_storage_dir
    - get_ocr_provider → MockOCRProvider (no Tesseract required)
    - get_llm_provider → FakeLLMProvider (no OpenAI API key required)
    """
    storage_provider = LocalStorageProvider(storage_root=tmp_storage_dir)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def _override_storage() -> LocalStorageProvider:
        return storage_provider

    def _override_ocr() -> MockOCRProvider:
        return mock_ocr

    def _override_llm() -> FakeLLMProvider:
        return fake_llm

    fastapi_app.dependency_overrides[get_db_session] = _override_db
    fastapi_app.dependency_overrides[get_storage_provider] = _override_storage
    fastapi_app.dependency_overrides[get_ocr_provider] = _override_ocr
    fastapi_app.dependency_overrides[get_llm_provider] = _override_llm

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://testserver",
    ) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


