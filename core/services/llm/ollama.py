"""
Ollama Provider
Local LLM provider using Ollama.
"""
import requests
import json
from typing import Optional


class OllamaProvider:
    """Local LLM provider using Ollama."""
    
    def __init__(
        self,
        endpoint: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: int = 30,
        max_retries: int = 2
    ):
        """Initialize Ollama provider.
        
        Args:
            endpoint: Ollama API endpoint
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
        """
        self.endpoint = endpoint.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
    
    def rewrite_text(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Rewrite text using Ollama.
        
        Args:
            prompt: The prompt containing context and text to rewrite
            temperature: Temperature for generation (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Rewritten text or None if generation fails
        """
        url = f"{self.endpoint}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40
            }
        }
        
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get('response', '').strip()
                    return generated_text if generated_text else None
                else:
                    print(f"Ollama request failed with status {response.status_code}: {response.text}")
                    if attempt < self.max_retries:
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"Ollama request timed out (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    continue
                return None
                
            except requests.exceptions.ConnectionError:
                print(f"Could not connect to Ollama at {self.endpoint}")
                print("Make sure Ollama is running: ollama serve")
                return None
                
            except Exception as e:
                print(f"Error calling Ollama: {e}")
                if attempt < self.max_retries:
                    continue
                return None
        
        return None
    
    def is_available(self) -> bool:
        """Check if Ollama is available.
        
        Returns:
            True if Ollama is running and model is available
        """
        try:
            # Check if Ollama is running
            response = requests.get(
                f"{self.endpoint}/api/tags",
                timeout=5
            )
            
            if response.status_code != 200:
                return False
            
            # Check if model is available
            data = response.json()
            models = data.get('models', [])
            model_names = [m.get('name', '') for m in models]
            
            # Check if our model is in the list (handle tag variations)
            model_base = self.model.split(':')[0]
            for name in model_names:
                if name.startswith(model_base):
                    return True
            
            print(f"Model {self.model} not found. Available models: {model_names}")
            print(f"Pull the model with: ollama pull {self.model}")
            return False
            
        except requests.exceptions.ConnectionError:
            print(f"Ollama not running at {self.endpoint}")
            print("Start Ollama with: ollama serve")
            return False
            
        except Exception as e:
            print(f"Error checking Ollama availability: {e}")
            return False
