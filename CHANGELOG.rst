================
Versions history
================

This repository follows changelog_.

We try to stick to **Semantic versioning**.


[1.4.0] - 2024-09-27
====================

Added
-----
* Basic support for RTSPS (but no claim on RTSP/2.0) - Thanks Joshua Wise <joshua@joshuawise.com>

[1.3.7] - 2023-09-01
====================

Fixed
-----
* fix RTSPReader to prevent sending URL credentials into the logs


[1.3.6] - 2021-06-30
====================

Fixed
-----
* fix an issue with RTCP statistics not properly detecting reordering
* fix a issue with RTCP possibly overflowing where there are too many lost packets


[1.3.5] - 2021-03-02
====================

Fixed
-----
* Adapt to servers not supporting GET_PARAMETERS and OPTIONS


[1.3.4] - 2021-02-18
====================

Fixed
-----
* Start CSeq to 1 instead of 0 for some peaky servers

Misc
----
* Enforce py36 or higher, as it does not work below that point.
* Fix license specifier which was incorrect


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
