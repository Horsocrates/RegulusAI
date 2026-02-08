"""
Regulus AI - MAS Routing Config
================================

Model routing per domain per complexity level.
"""

from dataclasses import dataclass, field


@dataclass
class DomainRoute:
    """Routing config for a single domain at a given complexity."""
    domain: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class RoutingConfig:
    """Model routing: complexity -> domain -> route."""
    routes: dict[str, dict[str, DomainRoute]] = field(default_factory=dict)

    def get_model(self, complexity: str, domain: str) -> str:
        """Get the model for a domain at a given complexity, with fallback."""
        complexity_routes = self.routes.get(complexity, {})
        route = complexity_routes.get(domain)
        if route:
            return route.model
        # Fallback to easy routes, then default
        easy_routes = self.routes.get("easy", {})
        easy_route = easy_routes.get(domain)
        if easy_route:
            return easy_route.model
        return "gpt-4o-mini"

    def get_route(self, complexity: str, domain: str) -> DomainRoute:
        """Get the full route for a domain at a given complexity."""
        complexity_routes = self.routes.get(complexity, {})
        route = complexity_routes.get(domain)
        if route:
            return route
        return DomainRoute(domain=domain)

    @classmethod
    def default(cls) -> "RoutingConfig":
        """Default routing configuration."""
        domains = ["D1", "D2", "D3", "D4", "D5", "D6"]

        # Easy: all gpt-4o-mini
        easy = {d: DomainRoute(domain=d, model="gpt-4o-mini") for d in domains}

        # Medium: D1+D5 get gpt-4o, rest gpt-4o-mini
        medium = {}
        for d in domains:
            if d in ("D1", "D5"):
                medium[d] = DomainRoute(domain=d, model="gpt-4o")
            else:
                medium[d] = DomainRoute(domain=d, model="gpt-4o-mini")

        # Hard: D1+D3+D5 get deepseek, rest gpt-4o
        hard = {}
        for d in domains:
            if d in ("D1", "D3", "D5"):
                hard[d] = DomainRoute(domain=d, model="deepseek")
            else:
                hard[d] = DomainRoute(domain=d, model="gpt-4o")

        return cls(routes={"easy": easy, "medium": medium, "hard": hard})
