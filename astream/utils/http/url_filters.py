from typing import List
from astream.utils.logger import logger
from astream.config.settings import settings


def filter_excluded_domains(urls: List[str], user_excluded_domains: str = "") -> List[str]:
    """Filtre URLs selon EXCLUDED_DOMAINS (serveur) + exclusions utilisateur."""
    try:
        # Récupérer exclusions serveur
        server_excluded = getattr(settings, 'EXCLUDED_DOMAINS', '')
        
        # Combiner exclusions serveur + utilisateur
        all_exclusions = []
        
        if server_excluded:
            all_exclusions.extend([domain.strip() for domain in server_excluded.split(',') if domain.strip()])
        
        if user_excluded_domains:
            all_exclusions.extend([domain.strip() for domain in user_excluded_domains.split(',') if domain.strip()])
        
        # Si aucune exclusion, retourner tel quel
        if not all_exclusions:
            return urls
        
        # Supprimer les doublons tout en gardant l'ordre
        seen = set()
        unique_exclusions = []
        for exclusion in all_exclusions:
            if exclusion not in seen:
                seen.add(exclusion)
                unique_exclusions.append(exclusion)
        
        filtered_urls = []
        for url in urls:
            excluded = False
            excluded_by = None
            
            for pattern in unique_exclusions:
                if pattern in url:
                    excluded = True
                    excluded_by = pattern
                    break
            
            if excluded:
                # Différencier serveur vs utilisateur dans les logs
                source = "serveur" if excluded_by in server_excluded.split(',') else "utilisateur"
                logger.debug(f"EXCLUDED {url} ({source}: {excluded_by})")
            else:
                filtered_urls.append(url)
        
        total_filtered = len(urls) - len(filtered_urls)
        if total_filtered > 0:
            logger.debug(f"{total_filtered} URLs filtrées (serveur + utilisateur)")
        
        return filtered_urls
        
    except Exception as e:
        logger.warning(f"Erreur filtrage exclusions: {e}")
        return urls