from typing import List
from astream.utils.logger import logger
from astream.config.app_settings import settings


def filter_excluded_domains(urls: List[str]) -> List[str]:
    """Filtre URLs selon EXCLUDED_DOMAIN."""
    try:
        excluded_domains = getattr(settings, 'EXCLUDED_DOMAIN', '')
        if not excluded_domains:
            return urls
        
        excluded_list = [domain.strip() for domain in excluded_domains.split(',') if domain.strip()]
        
        if not excluded_list:
            return urls
        
        filtered_urls = []
        for url in urls:
            excluded = False
            for domain in excluded_list:
                if domain in url:
                    logger.log("DEBUG", f"EXCLUDED {url} (domaine: {domain})")
                    excluded = True
                    break
            
            if not excluded:
                filtered_urls.append(url)
        
        logger.log("DEBUG", f"{len(urls) - len(filtered_urls)} URLs filtrées selon EXCLUDED_DOMAIN")
        return filtered_urls
        
    except Exception as e:
        logger.log("WARNING", f"Erreur filtrage domaine: {e}")
        return urls