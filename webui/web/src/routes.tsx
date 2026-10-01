import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/AppLayout'
import CharacterLayout from '@/components/CharacterLayout'
import Dashboard from '@/pages/Dashboard'
import Export from '@/pages/Export'
import Identity from '@/pages/Identity'
import NewCharacter from '@/pages/NewCharacter'
import Plan from '@/pages/Plan'
import Status from '@/pages/Status'
import Studio from '@/pages/Studio'
import Viewer from '@/pages/Viewer'

export const routes = [
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/new', element: <NewCharacter /> },
      { path: '/c/:cid/identity', element: <Identity /> },
      { path: '/c/:cid/plan', element: <Plan /> },
      {
        element: <CharacterLayout />,
        children: [
          { path: '/c/:cid/studio/:action?/:direction?', element: <Studio /> },
          { path: '/c/:cid/view', element: <Viewer /> },
          { path: '/c/:cid/export', element: <Export /> },
        ],
      },
      { path: '/status', element: <Status /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
