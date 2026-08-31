import os
import httpx
import asyncio
from models import CallState
from providers import ProviderBase

class PlivoProvider(ProviderBase):
    def __init__(self):
        self.auth_id = os.getenv("PLIVO_AUTH_ID")
        self.auth_token = os.getenv("PLIVO_AUTH_TOKEN")
        self.source_number = os.getenv("PLIVO_SOURCE_NUMBER")
        self.webhook_url = os.getenv("PUBLIC_WEBHOOK_URL")
        
        if not all([self.auth_id, self.auth_token, self.source_number, self.webhook_url]):
            print("WARNING: Missing Plivo environment variables. Calls will fail.")
            
    async def place_call(self, call_id: str, phone: str, callback):
        """
        Sends an HTTP POST to Plivo to initiate the call.
        Unlike the mock provider, we don't simulate states here. 
        Plivo will hit our webhook endpoint with the states, and the server will call the callback.
        """
        # Plivo API endpoint
        url = f"https://api.plivo.com/v1/Account/{self.auth_id}/Call/"
        
        # Plivo requires an answer_url which gives them XML instructions on what to do when the user answers.
        # For a dialer, usually you'd return an XML that bridges the user to an agent.
        # Here we just use a generic plivo text-to-speech URL as a placeholder.
        answer_url = "https://s3.amazonaws.com/static.plivo.com/answer.xml"
        
        # We append our internal call_id to the webhook URL so Plivo sends it back to us!
        webhook_with_id = f"{self.webhook_url}?call_id={call_id}"
        
        payload = {
            "from": self.source_number,
            "to": phone,
            "answer_url": answer_url,
            "answer_method": "GET",
            "machine_detection": "true",
            "ring_url": webhook_with_id,
            "ring_method": "POST",
            "hangup_url": webhook_with_id,
            "hangup_method": "POST",
            "fallback_url": webhook_with_id,
            "fallback_method": "POST"
        }
        
        try:
            async with httpx.AsyncClient(auth=(self.auth_id, self.auth_token)) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code in (200, 201):
                    # Plivo accepted the call request
                    # We can mark it as INITIATED
                    # Plivo's Request UUID is the real remote call ID, but we map it back to our internal call_id
                    data = response.json()
                    plivo_request_uuid = data.get("request_uuid")
                    await callback(call_id, CallState.INITIATED, f"init_{plivo_request_uuid}")
                else:
                    # Plivo rejected it
                    print(f"Plivo Error: {response.text}")
                    await callback(call_id, CallState.FAILED, f"fail_plivo_{call_id}")
                    
        except Exception as e:
            print(f"Exception calling Plivo: {e}")
            await callback(call_id, CallState.FAILED, f"fail_err_{call_id}")
