"""Stateless cloud LLM agent; provider transport is composed behind this interface."""

from maniloop.providers.responses import GPTPolicy


class LLMAgent:
    def __init__(self, model, api_key, base_url=None, *, request_options=None):
        self.provider = GPTPolicy(model=model, api_key=api_key, base_url=base_url,
                                  request_options=request_options)

    @property
    def request_options(self):
        return self.provider.request_options

    @property
    def last_response_id(self):
        return self.provider.last_response_id

    def diagnose(self, stage, task, observation, images):
        return self.provider.diagnose(stage, task, observation, images)

    @property
    def client(self):
        return self.provider.client

    @property
    def last_latency(self):
        return self.provider.last_latency

    @property
    def last_usage(self):
        return self.provider.last_usage

    def reset(self, seed=0):
        # Requests have no persistent remote conversation; episode history is supplied explicitly.
        pass

    def decide(self, task, observation, images, history, geometry_results):
        return self.provider.decide(
            task, observation, images, history, geometry_results
        )
