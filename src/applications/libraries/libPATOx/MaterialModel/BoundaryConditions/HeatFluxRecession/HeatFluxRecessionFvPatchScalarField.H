/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | Copyright (C) 2011-2016 OpenFOAM Foundation
     \\/     M anipulation  |
-------------------------------------------------------------------------------
License
    This file is part of OpenFOAM.

    OpenFOAM is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    OpenFOAM is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License
    along with OpenFOAM.  If not, see <http://www.gnu.org/licenses/>.

Class
    Foam::HeatFluxRecessionFvPatchScalarField

Description
    Combined temperature boundary condition that applies the existing
    HeatFlux surface-energy-balance model and the existing pyro_recession
    mesh-motion model on the same patch.

    HeatFluxBoundaryConditions is constructed first so that shared fields
    such as "recession" exist before pyro_recessionBoundaryConditions is
    constructed.

SourceFile
    HeatFluxRecessionFvPatchScalarField.C

\*---------------------------------------------------------------------------*/

#ifndef HeatFluxRecessionFvPatchScalarField_H
#define HeatFluxRecessionFvPatchScalarField_H

#include "fixedValueFvPatchFields.H"
#include "fvCFD.H"
#include "HeatFluxBoundaryConditions.H"
#include "pyro_recessionBoundaryConditions.H"

// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

namespace Foam
{

class HeatFluxRecessionFvPatchScalarField
:
public fixedValueFvPatchScalarField
{
  //- Debug switch
  Switch debug_;

  //- Reference to the mesh database
  const fvMesh& mesh;

  //- Phase name
  const word phaseName;

  //- Region name
  const word dictName;

  //- Dictionary
  dictionary dict_;

 public:

  // IMPORTANT: declaration order controls construction order.
  // HeatFlux must be constructed first so pyro_recession can reuse
  // fields already created by HeatFlux.
  HeatFluxBoundaryConditions HeatFluxBoundaryConditions_;

  pyro_recessionBoundaryConditions pyro_recessionBoundaryConditions_;

  //- Runtime type information
  TypeName("HeatFluxRecession");


  // Constructors

  //- Construct from patch and internal field
  HeatFluxRecessionFvPatchScalarField
  (
      const fvPatch&,
      const DimensionedField<scalar, volMesh>&
  );

  //- Construct from patch, internal field and dictionary
  HeatFluxRecessionFvPatchScalarField
  (
      const fvPatch&,
      const DimensionedField<scalar, volMesh>&,
      const dictionary&
  );

  //- Construct by mapping given HeatFluxRecessionFvPatchScalarField
  //  onto a new patch
  HeatFluxRecessionFvPatchScalarField
  (
      const HeatFluxRecessionFvPatchScalarField&,
      const fvPatch&,
      const DimensionedField<scalar, volMesh>&,
      const fvPatchFieldMapper&
  );

  //- Construct as copy
  HeatFluxRecessionFvPatchScalarField
  (
      const HeatFluxRecessionFvPatchScalarField&
  );

  //- Construct and return a clone
  virtual tmp<fvPatchScalarField> clone() const
  {
    return tmp<fvPatchScalarField>
    (
        new HeatFluxRecessionFvPatchScalarField(*this)
    );
  }

  //- Construct as copy setting internal field reference
  HeatFluxRecessionFvPatchScalarField
  (
      const HeatFluxRecessionFvPatchScalarField&,
      const DimensionedField<scalar, volMesh>&
  );

  //- Construct and return a clone setting internal field reference
  virtual tmp<fvPatchScalarField> clone
  (
      const DimensionedField<scalar, volMesh>& iF
  ) const
  {
    return tmp<fvPatchScalarField>
    (
        new HeatFluxRecessionFvPatchScalarField(*this, iF)
    );
  }


  // Member functions

  //- Update the coefficients associated with the patch field
  virtual void updateCoeffs();

  //- Write
  virtual void write(Ostream&) const;

  //- Initialize
  dictionary initDict();
};


// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

} // End namespace Foam

#endif

// ************************************************************************* //
