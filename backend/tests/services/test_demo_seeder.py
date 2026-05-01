import pytest
from unittest.mock import patch, MagicMock
from services.demo_seeder import seed_demo_data
from services.demo_constants import DEMO_FAMILY_PROFILE, DEMO_PORTFOLIO_DATA, DEMO_ALT_INVESTMENT
import config

@pytest.fixture
def mock_db_manager():
    with patch("services.demo_seeder.db_manager") as m:
        yield m

def test_seed_demo_data_success(mock_db_manager):
    """Test successful seeding of all demo data."""
    # Arrange
    # Mock the alt_projects collection to return a document that can be deleted
    mock_doc = MagicMock()
    mock_db_manager.db.collection.return_value.document.return_value.collection.return_value.list_documents.return_value = [mock_doc]

    # Act
    seed_demo_data()

    # Assert
    # 1. Family Profile assertions
    mock_db_manager.save_family_profile.assert_called_once()
    args, _ = mock_db_manager.save_family_profile.call_args
    assert args[0] == config.DEMO_UID
    assert "created_at" in args[1]
    # Check that it deeply copied the original data
    assert args[1]["authorizedEmails"] == DEMO_FAMILY_PROFILE["authorizedEmails"]

    # 2. Portfolio assertions
    mock_db_manager.save_processed_portfolio.assert_called_once()
    args, _ = mock_db_manager.save_processed_portfolio.call_args
    assert args[0] == config.DEMO_UID
    assert "last_updated" in args[1]
    assert args[1]["summary"]["total_value"] == DEMO_PORTFOLIO_DATA["summary"]["total_value"]

    # 3. Alternative Investments assertions
    # Ensure existing docs were deleted
    mock_doc.delete.assert_called_once()
    # Ensure new project was added
    mock_db_manager.add_alt_project.assert_called_once()
    args, _ = mock_db_manager.add_alt_project.call_args
    assert args[0] == config.DEMO_UID
    assert args[1] == DEMO_ALT_INVESTMENT

def test_seed_demo_data_exception_on_delete(mock_db_manager):
    """Test that seeding continues successfully even if deleting existing alt_projects throws an exception."""
    # Arrange
    # Force list_documents to raise an exception
    mock_db_manager.db.collection.return_value.document.return_value.collection.return_value.list_documents.side_effect = Exception("Firestore Error")

    # Act
    # This should not raise an exception because of the try/except block
    seed_demo_data()

    # Assert
    # Verify that we still add the new alt project despite the delete failure
    mock_db_manager.add_alt_project.assert_called_once()
    args, _ = mock_db_manager.add_alt_project.call_args
    assert args[0] == config.DEMO_UID
    assert args[1] == DEMO_ALT_INVESTMENT
