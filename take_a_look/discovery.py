"""Independent rule discovery and provider discovery, merged with provenance."""
from dataclasses import replace
from .providers import MockProvider
from .roles import Investigator


class HybridInvestigator(Investigator):
    def investigate(self, sources):
        rules=Investigator(MockProvider()).investigate(sources)
        if isinstance(self.provider,MockProvider):
            return rules
        proposed=super().investigate(sources)
        # Fallback output is rule discovery, never credited to an LLM.
        if getattr(self.provider,'last_used_fallback',False):
            return rules
        result=list(rules)
        index={(c.rule,c.file,c.line):i for i,c in enumerate(result)}
        for c in proposed:
            key=(c.rule,c.file,c.line)
            if key in index:
                i=index[key]
                result[i]=replace(result[i],discovery_source='BOTH',origin=c.origin,
                    provider_claim_id=c.provider_claim_id,confidence=c.confidence,
                    reasoning_summary=c.reasoning_summary,evidence_refs=c.evidence_refs)
            else:
                index[key]=len(result)
                result.append(replace(c,discovery_source='LLM'))
        return result


def discovery_metrics(claims,verdicts):
    totals={key:sum(c.discovery_source in sources for c in claims) for key,sources in {
        'rule_initial_claims':{'RULE','BOTH'},'llm_initial_claims':{'LLM','BOTH'},
        'overlap':{'BOTH'},'llm_only_claims':{'LLM'},'rule_only_claims':{'RULE'}}.items()}
    totals['by_discovery']={source:{status:sum(c.discovery_source==source and v.status==status for c,v in zip(claims,verdicts)) for status in ['CONFIRMED','REFUTED','UNCONFIRMED','NEEDS_HUMAN']} for source in ['RULE','LLM','BOTH']}
    return totals
