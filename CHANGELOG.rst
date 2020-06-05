================
Versions history
================

This repository follows changelog_.

**Semantic versioning** will be followed as soon as stable enough, and will reach 1.0.0.

[1.3.3] - 2020-06-05
====================

Fixed
-----
* Fix an issue when RTSP response headers are fragmented across multiple TCP reads

[1.3.2] - 2020-02-12
====================

Fixed
-----
* Some servers don't like when CSeq is not the first header...

[1.3.1] - 2019-12-11
====================

Fixed
-----
* Check transport status in session keep alive loops

[1.3.0] - 2019-10-10
====================

Added
-----
* Add a simplified ``RTSPReader`` class for easy RTP gathering


[1.2.1] - 2019-10-05
====================

Added
-----
* First Open Source version


.. ### PUT ANY REFERENCE TO HERE
.. _changelog: https://keepachangelog.com/en/1.0.0/
