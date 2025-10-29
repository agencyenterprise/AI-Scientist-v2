import pytest
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pod_worker import (
    EventEmitter,
    get_content_type,
    get_gpu_info,
    is_retryable,
    get_stage_description
)

class TestEventEmitter:
    def test_emit_single_event(self):
        emitter = EventEmitter("http://test.com", "test-pod")
        
        emitter.emit("test.event", {"key": "value"}, "run-123")
        
        assert len(emitter.batch) == 1
        event = emitter.batch[0]
        assert event["type"] == "test.event"
        assert event["data"] == {"key": "value"}
        assert event["subject"] == "run/run-123"
        assert event["source"] == "runpod://pod/test-pod"
    
    def test_batch_accumulation(self):
        emitter = EventEmitter("http://test.com", "test-pod")
        
        for i in range(5):
            emitter.emit(f"test.event.{i}", {"index": i}, "run-123")
        
        assert len(emitter.batch) == 5
    
    def test_auto_flush_at_batch_size(self):
        emitter = EventEmitter("http://test.com", "test-pod")
        emitter.batch_size = 3
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            for i in range(5):
                emitter.emit(f"test.event.{i}", {"index": i}, "run-123")
            
            assert mock_post.call_count >= 1
            assert len(emitter.batch) == 2

    def test_flush_single_event_uses_json_endpoint(self):
        emitter = EventEmitter("http://test.com", "test-pod")
        emitter.emit("test.event", {"data": "test"}, "run-123")
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            emitter.flush()
            
            call_args = mock_post.call_args
            assert '/api/ingest/event' in call_args[0][0]
            assert call_args[1]['headers']['Content-Type'] == 'application/json'
    
    def test_flush_multiple_events_uses_ndjson_endpoint(self):
        emitter = EventEmitter("http://test.com", "test-pod")
        emitter.emit("test.event.1", {}, "run-123")
        emitter.emit("test.event.2", {}, "run-123")
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            emitter.flush()
            
            call_args = mock_post.call_args
            assert '/api/ingest/events' in call_args[0][0]
            assert call_args[1]['headers']['Content-Type'] == 'application/x-ndjson'

class TestContentType:
    def test_pdf_content_type(self):
        assert get_content_type("paper.pdf") == "application/pdf"
    
    def test_png_content_type(self):
        assert get_content_type("plot.png") == "image/png"
    
    def test_tar_gz_content_type(self):
        assert get_content_type("archive.tar.gz") == "application/gzip"
    
    def test_unknown_extension(self):
        assert get_content_type("file.xyz") == "application/octet-stream"

class TestGPUInfo:
    def test_gpu_info_with_cuda(self):
        with patch('torch.cuda.is_available', return_value=True):
            with patch('torch.cuda.get_device_name', return_value="NVIDIA L40S"):
                with patch('torch.cuda.device_count', return_value=3):
                    info = get_gpu_info()
                    
                    assert info["gpu_name"] == "NVIDIA L40S"
                    assert info["gpu_count"] == 3
    
    def test_gpu_info_without_cuda(self):
        with patch('torch.cuda.is_available', return_value=False):
            info = get_gpu_info()
            
            assert info["gpu_name"] == "unknown"
            assert info["gpu_count"] == 0

class TestErrorHandling:
    def test_is_retryable_connection_error(self):
        assert is_retryable(ConnectionError)
    
    def test_is_retryable_timeout(self):
        assert is_retryable(TimeoutError)
    
    def test_is_not_retryable_value_error(self):
        assert not is_retryable(ValueError)
    
    def test_is_not_retryable_runtime_error(self):
        assert not is_retryable(RuntimeError)

class TestStageDescription:
    def test_stage_1_description(self):
        assert get_stage_description("Stage_1") == "Preliminary Investigation"
    
    def test_stage_4_description(self):
        assert get_stage_description("Stage_4") == "Ablation Studies"
    
    def test_unknown_stage(self):
        assert get_stage_description("Stage_Unknown") == "Stage_Unknown"

class TestArtifactUpload:
    def test_upload_artifact_success(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            file_path = f.name
        
        try:
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"url": "http://presigned-url"}
                
                with patch('requests.put') as mock_put:
                    mock_put.return_value.status_code = 200
                    
                    with patch('pod_worker.emit_event'):
                        from pod_worker import upload_artifact
                        result = upload_artifact("run-123", file_path, "test")
                        
                        assert result is True
        finally:
            os.unlink(file_path)
    
    def test_upload_artifact_failure(self):
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            with patch('pod_worker.emit_event'):
                from pod_worker import upload_artifact
                result = upload_artifact("run-123", "/nonexistent/file.txt", "test")
                
                assert result is False

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

