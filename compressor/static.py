from django.template import Context
from django.template.loader import render_to_string

from compressor.conf import settings
from compressor.base import Compressor, STATIC_FILE
from compressor.signals import post_compress

class StaticCompressor(Compressor):
    template_name = "compressor/static.html"
    template_name_inline = "compressor/static_inline.html"

    def __init__(self, content=None, output_prefix="static", context=None):
        self.type = content.split(".")[-1]
        output_prefix = self.type
        super(StaticCompressor, self).__init__(content, output_prefix, context)
        self.filters = list(settings.COMPRESS_STATIC_FILTERS)


    def split_contents(self):
        basename = self.content
        filename = self.get_filename(basename)
        elem = {'attrs_dict':{}, 'tag':'', 'attrs':[], 'text':basename}
        self.split_content.append((STATIC_FILE, filename, basename, elem))
        return self.split_content
    
    def render_output(self, mode, context=None):
        """
        Renders the compressor output with the appropriate template for
        the given mode and template context.
        """
        if context is None:
            context = {}
        final_context = Context()
        final_context.update(self.context)
        final_context.update(context)
        final_context.update(self.extra_context)
        post_compress.send(sender='django-compressor', type=self.type, mode=mode, context=final_context) 
        return render_to_string("compressor/static_%s.html" %
                                (mode,), final_context)
